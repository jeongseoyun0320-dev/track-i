#!/usr/bin/env python3
"""
Track-I : CSI camera (IMX219) + YOLO + dual haptic (DA7280 x2 via
TCA9548A) + TTS + UI
Threads
 - CameraThread : GStreamer capture (원본 파이프라인 그대로, flip -1 유
지)
 - DetectorThread : YOLO 추론 -> 위치(좌/중/우) + 거리(FAR/NEAR/DANGER)
판정
 - HapticThread : I2C 소유 스레드 (DA7280 초기화/진동 패턴)
 - TTSThread : espeak-ng 음성 안내 (위험 시 즉시 끼어들기)
 - main : 화면 UI (cv2.imshow 는 메인 스레드에서만)
종료: 영상 창에서 q / ESC / EXIT 버튼, 터미널에서 q / Ctrl+C
"""

import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import List, Optional
import cv2
from smbus2 import SMBus
# =========================================================
# 설정
# =========================================================
# ---- Camera ----
SENSOR_ID = 0
WIDTH = 1920
HEIGHT = 1080
FPS = 30
DISPLAY_SIZE = (960, 540)
# ---- YOLO ----
MODEL_PATH = "yolov8n.pt" # TensorRT 엔진(.engine)이면 경로만 바꾸면 됨
IMGSZ = 416
CONF_THRES = 0.40
ALLOWED_CLASSES = None # 예: {"person", "chair", "car"} / None =
전체
# ---- 위치 (프레임 가로 기준 비율) ----
LEFT_LIMIT = 1 / 3
RIGHT_LIMIT = 2 / 3
# ---- 거리 (박스 면적 / 프레임 면적 = A, 박스 하단 y / 프레임 높이 = B) ----
# 현장에서 보면서 튜닝하세요.
AREA_NEAR = 0.04
AREA_DANGER = 0.15
BOTTOM_DANGER = 0.97 # 박스가 화면 바닥에 닿을 정도 + 면적이 어느 정도 되면 위험
BOTTOM_DANGER_MIN_AREA = 0.06
FAR, NEAR, DANGER = 1, 2, 3
LEVEL_NAME = {FAR: "FAR", NEAR: "NEAR", DANGER: "DANGER"}
# ---- Haptic ----
I2C_BUS = 7
TCA9548A_ADDR = 0x70
DA7280_ADDR = 0x4A
LEFT_CHANNEL = 0
RIGHT_CHANNEL = 1
TOP_CFG1 = 0x13
TOP_CTL1 = 0x22
TOP_CTL2 = 0x23
DRO_MODE = 0x01
# level -> (세기 0~127, 진동 시간[s], 반복 주기[s])
HAPTIC_PATTERN = {
 FAR: (55, 0.08, 1.20),
 NEAR: (90, 0.15, 0.60),
 DANGER: (127, 0.25, 0.30), # 위험: 양쪽 모터 동시에 강하게 + 연속에
가깝게 }
HAPTIC_STALE_SEC = 0.6 # 이 시간 동안 감지가 갱신 안 되면 진동
정지
# ---- TTS ----
TTS_ENABLED = True
TTS_LANG = "en" # "en" 또는 "ko"
TTS_VOICE = {"en": "en", "ko": "ko"}
TTS_SPEED = 170
TTS_REPEAT_SEC = {FAR: 10.0, NEAR: 5.0, DANGER: 2.5}
TTS_MIN_GAP_SEC = 1.0 # 내용이 바뀌어도 최소 이 간격 (DANGER 제
외)
KO_LABEL = {
 "person": "사람", "car": "자동차", "bicycle": "자전거", "motorcycle":
"오토바이",
 "bus": "버스", "truck": "트럭", "chair": "의자", "bench": "벤치",
"dog": "개",
 "cat": "고양이", "backpack": "가방", "bottle": "병", "couch": "소파",
 "potted plant": "화분", "dining table": "테이블", "traffic light": "신
호등",}
SIDE_KO = {"LEFT": "왼쪽", "CENTER": "가운데", "RIGHT": "오른쪽"}
# =========================================================
# 공유 데이터
# =========================================================
@dataclass
class Detection:
 label: str
 conf: float
 x1: int
 y1: int
 x2: int
 y2: int
 area: float
 bottom: float
 side: str
 level: int
@dataclass
class Hazard:
 label: str
 side: str
 level: int
 ts: float
class HazardHub:
 """감지 스레드 -> 햅틱/TTS 스레드로 가장 위험한 대상 전달"""
 def __init__(self):
 self._lock = threading.Lock()
 self._hazard: Optional[Hazard] = None
 def set(self, hazard: Optional[Hazard]):
 with self._lock:
 self._hazard = hazard
 def get_fresh(self, max_age: float) -> Optional[Hazard]:
 with self._lock:
 h = self._hazard
 if h is None or (time.monotonic() - h.ts) > max_age:
 return None
 return h
# =========================================================
# Camera
# =========================================================
def build_pipeline():
 return (
 f"nvarguscamerasrc sensor-id={SENSOR_ID} ! "
 f"video/x-raw(memory:NVMM),width={WIDTH},"
 f"height={HEIGHT},framerate={FPS}/1 ! "
 "nvvidconv flip-method=0 ! "
 "video/x-raw,format=BGRx ! "
 "videoconvert ! "
 "video/x-raw,format=BGR ! "
 "appsink drop=true max-buffers=1 sync=false"
 )
class CameraThread(threading.Thread):
 def __init__(self):
 super().__init__(daemon=True)
 self.cap = None
 self.running = True
 self.failed = False
 self._lock = threading.Lock()
 self._frame = None
 self._fid = 0
 def open(self):
 pipeline = build_pipeline()
 print("OpenCV version:", cv2.__version__)
 for line in cv2.getBuildInformation().splitlines():
 if "GStreamer:" in line:
 print(line.strip())
 print("Opening camera...")
 print(pipeline)
 self.cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
 if not self.cap.isOpened():
 raise SystemExit("ERROR: Camera open failed")
 print("Camera opened successfully")
 def run(self):
 while self.running:
 ret, frame = self.cap.read()
 if not ret:
 print("ERROR: Frame read failed")
 self.failed = True
 break
 frame = cv2.flip(frame, -1)
 with self._lock:
 self._frame = frame
 self._fid += 1
 def get(self):
 with self._lock:
 return self._frame, self._fid
 def stop(self):
 self.running = False
 self.join(timeout=2.0)
 if self.cap is not None:
 self.cap.release()
# =========================================================
# Detector (YOLO + 위치/거리 판정)
# =========================================================
def classify_side(cx_ratio: float) -> str:
 if cx_ratio < LEFT_LIMIT:
 return "LEFT"
 if cx_ratio > RIGHT_LIMIT:
 return "RIGHT"
 return "CENTER"
def classify_level(area: float, bottom: float) -> int:
 if area >= AREA_DANGER or (bottom >= BOTTOM_DANGER and area >=
BOTTOM_DANGER_MIN_AREA):
 return DANGER
 if area >= AREA_NEAR:
 return NEAR
 return FAR
class DetectorThread(threading.Thread):
 def __init__(self, cam: CameraThread, hub: HazardHub):
 super().__init__(daemon=True)
 self.cam = cam
 self.hub = hub
 self.running = True
 self._lock = threading.Lock()
 self._dets: List[Detection] = []
 self._hazard: Optional[Hazard] = None
 self.infer_fps = 0.0
 from ultralytics import YOLO
 import torch
 self.device = 0 if torch.cuda.is_available() else "cpu"
 self.half = self.device != "cpu"
 print(f"Loading YOLO: {MODEL_PATH} (device={self.device})")
 self.model = YOLO(MODEL_PATH)
 # 워밍업
 import numpy as np
 dummy = np.zeros((IMGSZ, IMGSZ, 3), dtype=np.uint8)
 self.model.predict(dummy, imgsz=IMGSZ, device=self.device,
half=self.half, verbose=False)
 def run(self):
 last_fid = -1
 while self.running:
 frame, fid = self.cam.get()
 if frame is None or fid == last_fid:
 time.sleep(0.005)
 continue
 last_fid = fid
 t0 = time.monotonic()
 h, w = frame.shape[:2]
 res = self.model.predict(
 frame, imgsz=IMGSZ, conf=CONF_THRES,
 device=self.device, half=self.half, verbose=False,
 )[0]
 dets: List[Detection] = []
 names = res.names
 for b in res.boxes:
 label = names[int(b.cls[0])]
 if ALLOWED_CLASSES and label not in ALLOWED_CLASSES:
 continue
 x1, y1, x2, y2 = [int(v) for v in b.xyxy[0].tolist()]
 area = max(0, x2 - x1) * max(0, y2 - y1) / float(w * h)
 bottom = y2 / float(h)
 cx = (x1 + x2) / 2.0 / w
 dets.append(Detection(
 label=label, conf=float(b.conf[0]),
 x1=x1, y1=y1, x2=x2, y2=y2,
 area=area, bottom=bottom,
 side=classify_side(cx),
 level=classify_level(area, bottom),
 ))
 hazard = None
 if dets:
 top = max(dets, key=lambda d: (d.level, d.side ==
"CENTER", d.area))
 hazard = Hazard(top.label, top.side, top.level,
time.monotonic())
 with self._lock:
 self._dets = dets
 self._hazard = hazard
 self.hub.set(hazard)
 dt = time.monotonic() - t0
 if dt > 0:
 self.infer_fps = 0.8 * self.infer_fps + 0.2 * (1.0 / dt)
 def snapshot(self):
 with self._lock:
 return list(self._dets), self._hazard
 def stop(self):
 self.running = False
 self.join(timeout=2.0)
# =========================================================
# Haptic (DA7280 x2 via TCA9548A) - I2C 는 이 스레드만 사용
# =========================================================
def select_channel(bus, channel):
 if channel < 0 or channel > 7:
 raise ValueError("TCA9548A channel must be 0..7")
 bus.write_byte(TCA9548A_ADDR, 1 << channel)
 time.sleep(0.002)
def disable_all_channels(bus):
 bus.write_byte(TCA9548A_ADDR, 0x00)
 time.sleep(0.002)
def read_reg(bus, reg):
 return bus.read_byte_data(DA7280_ADDR, reg)
def write_reg(bus, reg, value):
 bus.write_byte_data(DA7280_ADDR, reg, value & 0xFF)
def update_bits(bus, reg, mask, value):
 old = read_reg(bus, reg)
 new = (old & ~mask) | (value & mask)
 write_reg(bus, reg, new)
def init_da7280(bus, channel):
 select_channel(bus, channel)
 update_bits(bus, TOP_CFG1, 0x20, 0x00) # LRA actuator
 update_bits(bus, TOP_CFG1, 0x08, 0x00) # Disable frequency
tracking
 update_bits(bus, TOP_CFG1, 0x04, 0x04) # Enable acceleration
 update_bits(bus, TOP_CTL1, 0x07, DRO_MODE) # Direct Register
Override
 write_reg(bus, TOP_CTL2, 0) # Motor OFF
class HapticThread(threading.Thread):
 def __init__(self, hub: HazardHub):
 super().__init__(daemon=True)
 self.hub = hub
 self.running = True
 self.ready = False
 self.bus: Optional[SMBus] = None
 self._init_done = threading.Event()
 def _motors(self, channels, strength):
 strength = max(0, min(127, int(strength)))
 for ch in channels:
 select_channel(self.bus, ch)
 write_reg(self.bus, TOP_CTL2, strength)
 def _all_off(self):
 try:
 self._motors([LEFT_CHANNEL, RIGHT_CHANNEL], 0)
 except Exception:
 pass
 def run(self):
 try:
 self.bus = SMBus(I2C_BUS)
 print("Initializing LEFT DA7280...")
 init_da7280(self.bus, LEFT_CHANNEL)
 print("Initializing RIGHT DA7280...")
 init_da7280(self.bus, RIGHT_CHANNEL)
 self.ready = True
 except Exception as e:
 print(f"[Haptic] init failed -> haptic disabled: {e}")
 self._init_done.set()
 return
 self._init_done.set()
 next_pulse = 0.0
 try:
 while self.running:
 h = self.hub.get_fresh(HAPTIC_STALE_SEC)
 if h is None:
 time.sleep(0.03)
 continue
 now = time.monotonic()
 if now < next_pulse:
 time.sleep(0.005)
 continue
 strength, on_s, period = HAPTIC_PATTERN[h.level]
 if h.level == DANGER or h.side == "CENTER":
 channels = [LEFT_CHANNEL, RIGHT_CHANNEL]
 elif h.side == "LEFT":
 channels = [LEFT_CHANNEL]
 else:
 channels = [RIGHT_CHANNEL]
 try:
 self._motors(channels, strength)
 end = time.monotonic() + on_s
 while self.running and time.monotonic() < end:
 time.sleep(0.005)
 self._motors(channels, 0)
 except Exception as e:
 print(f"[Haptic] I2C error: {e}")
 time.sleep(0.2)
 next_pulse = now + period
 finally:
 self._all_off()
 try:
 disable_all_channels(self.bus)
 except Exception:
 pass
 if self.bus is not None:
 self.bus.close()
 def wait_ready(self, timeout=5.0):
 self._init_done.wait(timeout)
 def stop(self):
 self.running = False
 self.join(timeout=2.0)
# =========================================================
# TTS (espeak-ng / espeak / spd-say / festival 중 있는 것 사용)
# =========================================================
class TTSThread(threading.Thread):
 def __init__(self, hub: HazardHub):
 super().__init__(daemon=True)
 self.hub = hub
 self.running = True
 self.engine = None
 for name in ("espeak-ng", "espeak", "spd-say", "festival"):
 exe = shutil.which(name)
 if exe:
 self.engine = (name, exe)
 break
 self.exe = self.engine[1] if self.engine else None # UI 표시용
 self.proc: Optional[subprocess.Popen] = None
 self.last_key = None
 self.last_time = 0.0
 self.last_seen = 0.0
 self._startup_said = False
 if self.engine:
 print(f"[TTS] engine: {self.engine[0]}")
 else:
 print("[TTS] TTS 엔진 없음 -> 비활성화 (sudo apt install
espeak-ng)")
 def _text(self, h: Hazard) -> str:
 if TTS_LANG == "ko":
 label = KO_LABEL.get(h.label, h.label)
 side = SIDE_KO[h.side]
 if h.level == DANGER:
 return f"경고! {side} {label} 매우 가까움"
 if h.level == NEAR:
 return f"{side} {label} 가까움"
 return f"{side} {label} 멀리"
 side = h.side.lower()
 if h.level == DANGER:
 return f"Warning! {h.label} very close, {side}"
 if h.level == NEAR:
 return f"{h.label} near, {side}"
 return f"{h.label} far, {side}"
 def _busy(self):
 return self.proc is not None and self.proc.poll() is None
 def _cmd(self, text):
 name, exe = self.engine
 voice = TTS_VOICE.get(TTS_LANG, "en")
 if name in ("espeak-ng", "espeak"):
 return [exe, "-v", voice, "-s", str(TTS_SPEED), "-a", "200",
text], None
 if name == "spd-say":
 return [exe, "-w", "-l", voice, text], None
 # festival: stdin 으로 텍스트 전달
 return [exe, "--tts"], text
 def _speak(self, text, interrupt):
 if not self.engine:
 return False
 if self._busy():
 if not interrupt:
 return False
 self.proc.terminate()
 cmd, stdin_text = self._cmd(text)
 try:
 self.proc = subprocess.Popen(
 cmd,
 stdin=subprocess.PIPE if stdin_text else
subprocess.DEVNULL,
 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
 )
 if stdin_text:
 self.proc.stdin.write(stdin_text.encode("utf-8"))
 self.proc.stdin.close()
 print(f"[TTS] \"{text}\"")
 return True
 except Exception as e:
 print(f"[TTS] error: {e}")
 return False
 def run(self):
 if not self.engine:
 return
 
 # 시작 안내: 소리 나오는지 바로 확인 가능
 self._speak("Track I ready" if TTS_LANG != "ko" else "트랙 아이 시
작", interrupt=True)
 self._startup_said = True
 while self.running:
 h = self.hub.get_fresh(1.0)
 now = time.monotonic()
 if h is None:
 # 2초 이상 아무것도 없으면 다음 감지 때 다시 안내
 if now - self.last_seen > 2.0:
 self.last_key = None
 time.sleep(0.05)
 continue
 self.last_seen = now
 key = (h.label, h.side, h.level)
 elapsed = now - self.last_time
 changed = key != self.last_key
 repeat = TTS_REPEAT_SEC[h.level]
 danger = h.level == DANGER
 should = False
 if changed:
 should = danger or elapsed >= TTS_MIN_GAP_SEC
 elif elapsed >= repeat:
 should = True
 if should and self._speak(self._text(h), interrupt=danger):
 self.last_key = key
 self.last_time = now
 time.sleep(0.05)
 def stop(self):
 self.running = False
 if self._busy():
 self.proc.terminate()
 self.join(timeout=2.0)
# =========================================================
# 터미널 키 입력 (터미널에서 q 눌러도 종료)
# =========================================================
class TermKey:
 def __init__(self):
 self.ok = False
 self._old = None
 try:
 import sys, termios, tty
 if sys.stdin.isatty():
 self._fd = sys.stdin.fileno()
 self._old = termios.tcgetattr(self._fd)
 tty.setcbreak(self._fd)
 self.ok = True
 except Exception:
 self.ok = False
 def pressed_quit(self):
 if not self.ok:
 return False
 try:
 import sys, select
 while select.select([sys.stdin], [], [], 0)[0]:
 ch = sys.stdin.read(1)
 if ch in ("q", "Q", "\x1b"):
 return True
 except Exception:
 pass
 return False
 def restore(self):
 if self.ok and self._old is not None:
 try:
 import termios
 termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old)
 except Exception:
 pass
# =========================================================
# UI
# =========================================================
LEVEL_COLOR = { # BGR
 FAR: (0, 200, 0),
 NEAR: (0, 165, 255),
 DANGER: (0, 0, 255),
}
EXIT_REQUESTED = False
EXIT_BTN = (DISPLAY_SIZE[0] - 100, 38, DISPLAY_SIZE[0] - 10, 66) # x1,
y1, x2, y2
def on_mouse(event, x, y, flags, param):
 global EXIT_REQUESTED
 if event == cv2.EVENT_LBUTTONDOWN:
 x1, y1, x2, y2 = EXIT_BTN
 if x1 <= x <= x2 and y1 <= y <= y2:
 EXIT_REQUESTED = True
def draw_dashed_vline(img, x, color=(255, 255, 255), dash=12, gap=10):
 h = img.shape[0]
 y = 0
 while y < h:
 cv2.line(img, (x, y), (x, min(y + dash, h)), color, 1)
 y += dash + gap
def draw_ui(frame, dets, hazard, disp_fps, n_ok, haptic_on, tts_on):
 dw, dh = DISPLAY_SIZE
 display = cv2.resize(frame, (dw, dh))
 sx = dw / frame.shape[1]
 sy = dh / frame.shape[0]
 font = cv2.FONT_HERSHEY_SIMPLEX
 # 구역선 + 라벨
 draw_dashed_vline(display, int(dw * LEFT_LIMIT))
 draw_dashed_vline(display, int(dw * RIGHT_LIMIT))
 for text, cx in (("LEFT", dw * LEFT_LIMIT / 2),
 ("CENTER", dw * 0.5),
 ("RIGHT", dw * (1 + RIGHT_LIMIT) / 2)):
 size = cv2.getTextSize(text, font, 0.6, 2)[0]
 cv2.putText(display, text, (int(cx - size[0] / 2), dh - 20),
 font, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
 # 박스
 primary = None
 if hazard is not None:
 cands = [d for d in dets if d.label == hazard.label and d.side ==
hazard.side
 and d.level == hazard.level]
 primary = max(cands, key=lambda d: d.area) if cands else None
 for d in dets:
 color = LEVEL_COLOR[d.level]
 x1, y1, x2, y2 = int(d.x1 * sx), int(d.y1 * sy), int(d.x2 * sx),
int(d.y2 * sy)
 thick = 3 if d is primary else 2
 cv2.rectangle(display, (x1, y1), (x2, y2), color, thick)
 label = f"{d.label} {d.conf:.2f}"
 size = cv2.getTextSize(label, font, 0.55, 2)[0]
 cv2.rectangle(display, (x1, y1 - size[1] - 8), (x1 + size[0] + 4,
y1), color, -1)
 cv2.putText(display, label, (x1 + 2, y1 - 5), font, 0.55,
 (255, 255, 255), 2, cv2.LINE_AA)
 cv2.putText(display, f"{d.side} {LEVEL_NAME[d.level]}
A:{d.area:.2f} B:{d.bottom:.2f}",
 (x1, min(y2 + 16, dh - 40)), font, 0.45, color, 1,
cv2.LINE_AA)
 # 상단 정보
 cv2.putText(display, f"FPS: {disp_fps:.1f}", (12, 28), font, 0.7, (0,
255, 0), 2, cv2.LINE_AA)
 cv2.putText(display, f"Objects: {n_ok}", (12, 56), font, 0.7, (0, 255,
0), 2, cv2.LINE_AA)
 cv2.putText(display, f"Haptic:{'ON' if haptic_on else 'OFF'}
TTS:{'ON' if tts_on else 'OFF'}",
 (dw - 230, 28), font, 0.55, (200, 200, 200), 1,
cv2.LINE_AA)
 # 종료 버튼
 bx1, by1, bx2, by2 = EXIT_BTN
 cv2.rectangle(display, (bx1, by1), (bx2, by2), (0, 0, 160), -1)
 cv2.rectangle(display, (bx1, by1), (bx2, by2), (255, 255, 255), 1)
 cv2.putText(display, "EXIT", (bx1 + 20, by2 - 8), font, 0.6,
 (255, 255, 255), 2, cv2.LINE_AA)
 # 위험 배너
 if hazard is not None:
 text = f"PRIMARY HAZARD: {hazard.label} {hazard.side}
{LEVEL_NAME[hazard.level]}"
 danger = hazard.level == DANGER
 blink = danger and int(time.monotonic() * 4) % 2 == 0
 bg = (0, 0, 180) if blink else (0, 0, 0)
 cv2.rectangle(display, (10, 70), (dw - 10, 108), bg, -1)
 cv2.putText(display, ("!! " if danger else "") + text, (18, 97),
font, 0.75,
 (255, 255, 255) if blink else (0, 0, 255), 2,
cv2.LINE_AA)
 return display
# =========================================================
# main
# =========================================================
def main():
 hub = HazardHub()
 cam = CameraThread()
 cam.open()
 cam.start()
 try:
 detector = DetectorThread(cam, hub)
 except ImportError as e:
 cam.stop()
 raise SystemExit(f"ERROR: {e}\n pip install ultralytics (Jetson
용 torch 필요)")
 detector.start()
 haptic = HapticThread(hub)
 haptic.start()
 haptic.wait_ready()
 tts = TTSThread(hub)
 if TTS_ENABLED:
 tts.start()
 cv2.namedWindow("Track-I YOLO + Haptic")
 cv2.setMouseCallback("Track-I YOLO + Haptic", on_mouse)
 last_fid = -1
 disp_fps = 0.0
 t_prev = time.monotonic()
 termkey = TermKey()
 print("Running. 종료: 영상 창에서 q / ESC / EXIT 버튼, 또는 터미널에서
q / Ctrl+C")
 try:
 while True:
 if termkey.pressed_quit():
 print("Quit key pressed (terminal).")
 break
 if EXIT_REQUESTED:
 print("Exit button pressed.")
 break
 if cam.failed:
 print("Camera stopped.")
 break
 frame, fid = cam.get()
 if frame is None or fid == last_fid:
 if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q"), 27):
 break
 time.sleep(0.002)
 continue
 last_fid = fid
 now = time.monotonic()
 dt = now - t_prev
 t_prev = now
 if dt > 0:
 disp_fps = 0.9 * disp_fps + 0.1 * (1.0 / dt) if disp_fps
else 1.0 / dt
 dets, hazard = detector.snapshot()
 if hazard is not None and time.monotonic() - hazard.ts >
HAPTIC_STALE_SEC:
 hazard = None
 dets = []
 display = draw_ui(frame, dets, hazard, disp_fps, len(dets),
 haptic.ready, bool(tts.exe) and TTS_ENABLED)
 cv2.imshow("Track-I YOLO + Haptic", display)
 key = cv2.waitKey(1) & 0xFF
 if key in (ord("q"), ord("Q"), 27): # q 또는 ESC
 break
 except KeyboardInterrupt:
 print("Ctrl+C")
 finally:
 termkey.restore()
 if TTS_ENABLED and tts.is_alive():
 tts.stop()
 haptic.stop()
 detector.stop()
 cam.stop()
 cv2.destroyAllWindows()
if __name__ == "__main__":
 main()
 
