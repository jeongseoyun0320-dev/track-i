Track-I: 시각장애인 주행 보조 스마트 벨트 시스템

On-Device Vision AI and Multi-Sensory Feedback-Based Smart Belt System for Visually Impaired Running Assistance

Track-I는 시각장애인 주자의 육상 트랙 주행을 보조하기 위해 개발한 스마트 벨트 시스템입니다. 카메라 영상에서 주변 객체를 실시간으로 탐지하고, 객체의 화면상 위치와 상대적 근접도를 분석하여 좌·우 햅틱 진동과 음성 안내로 위험 정보를 전달합니다.

본 프로젝트는 한이음 드림업 프로젝트의 결과물이며, 관련 연구 내용은 「온디바이스 비전 AI 및 다감각 피드백 기반 시각장애인 주행 보조 스마트 벨트 시스템 설계 및 구현」 논문에 정리되어 있습니다.

⸻

1. 프로젝트 개요

시각장애인 마라토너는 주행 중 가이드 러너와의 물리적 연결이나 음성 안내에 의존하는 경우가 많습니다. 하지만 두 주자의 보폭과 속도 차이, 경기장의 주변 소음 등으로 인해 독립적인 주행 리듬 유지와 정보 전달에 어려움이 발생할 수 있습니다.

Track-I는 이러한 한계를 보완하기 위해 온디바이스 객체 탐지와 다감각 피드백을 결합한 웨어러블 주행 보조 시스템을 구현하는 것을 목표로 합니다.

* 프로젝트명: Track-I
* 주요 대상: 시각장애인 육상 주자
* 주요 환경: 육상 트랙
* 핵심 기술: Computer Vision, Object Detection, Edge AI, Haptic Feedback, Text-to-Speech
* 처리 방식: 카메라 입력부터 위험 판단 및 피드백 출력까지 온디바이스 처리

2. 주요 기능

기능	설명
실시간 객체 탐지	YOLO 기반 모델로 카메라 영상 속 객체 탐지
방향 판별	탐지 객체의 중심 좌표를 기준으로 LEFT, CENTER, RIGHT 구분
상대적 위험도 판단	바운딩 박스 면적과 화면 하단 위치를 이용해 FAR, NEAR, DANGER 분류
주요 위험 객체 선정	위험 수준, 방향, 객체 크기를 기준으로 우선 대상 선정
방향별 햅틱 피드백	좌·우 DA7280 모터를 선택적으로 구동하여 위험 방향 전달
음성 안내	TTS를 통해 객체 종류, 방향, 위험 수준 안내
실시간 모니터링 UI	객체 바운딩 박스, 방향, 위험 단계, FPS 및 장치 상태 표시

3. 시스템 구성

하드웨어

구성 요소	사용 부품	역할
메인 연산 장치	NVIDIA Jetson Orin Nano	온디바이스 AI 추론 및 시스템 제어
카메라	IMX219 광각 CSI Camera	전방 영상 입력
햅틱 드라이버	DA7280 × 2	좌·우 진동 모터 제어
I²C 멀티플렉서	TCA9548A	햅틱 드라이버 독립 제어
음성 출력 장치	스피커 또는 이어폰	위험 상황 음성 안내

소프트웨어 및 개발 환경

* Ubuntu 기반 Jetson 환경
* NVIDIA JetPack 7.2.1
* Python 3.12.3
* OpenCV 4.8.0
* PyTorch 2.12.0 / CUDA 13.2
* GStreamer
* Ultralytics YOLO

실제 실행 환경과 라이브러리 호환성은 Jetson 장치 및 설치된 CUDA·PyTorch 버전에 따라 달라질 수 있습니다.

4. 시스템 동작 원리

전체 시스템은 영상 입력 → 객체 탐지 → 방향 및 위험도 판단 → 주요 위험 객체 선정 → 햅틱·음성 피드백 순서로 동작합니다.

4.1 영상 입력 및 객체 탐지

IMX219 CSI 카메라에서 전방 영상을 입력받고, YOLO 모델을 이용해 객체를 탐지합니다. 탐지된 객체의 바운딩 박스 좌표와 클래스, 신뢰도 등을 활용합니다.

4.2 객체 방향 판별

객체의 바운딩 박스 중심 좌표를 기준으로 영상의 가로 영역을 세 구간으로 나눕니다.

* LEFT: 화면 왼쪽 영역
* CENTER: 화면 중앙 영역
* RIGHT: 화면 오른쪽 영역

4.3 상대적 위험도 판단

단안 카메라로 실제 거리를 직접 측정하는 대신 다음 두 지표를 활용해 상대적 근접도를 판단합니다.

* Bounding Box Area: 객체 바운딩 박스가 전체 영상에서 차지하는 면적 비율
* Bottom Position: 바운딩 박스 하단 좌표가 영상 높이에서 차지하는 비율

객체가 화면에서 크게 보이거나 화면 하단에 가까울수록 사용자와의 충돌 가능성이 높다고 가정합니다.

코드에 구현된 위험 단계는 다음과 같습니다.

위험 단계	의미
FAR	상대적으로 멀리 있는 객체
NEAR	객체 면적 비율이 설정된 근접 기준 이상인 경우
DANGER	객체 면적이 위험 기준 이상이거나 화면 하단에 가까우면서 일정 면적 이상인 경우

세부 임계값은 AREA_NEAR, AREA_DANGER, BOTTOM_DANGER, BOTTOM_DANGER_MIN_AREA 설정으로 조정할 수 있습니다.

4.4 주요 위험 객체 선정

여러 객체가 동시에 탐지되면 모든 객체에 피드백을 제공하는 대신 우선순위가 가장 높은 객체를 주요 위험 객체(Primary Hazard)로 선정합니다.

현재 코드에서는 다음 기준을 순서대로 비교합니다.

1. 위험 단계가 높은 객체
2. 동일 위험 단계라면 화면 중앙에 위치한 객체
3. 앞선 조건이 같다면 바운딩 박스 면적이 큰 객체

4.5 햅틱 피드백

TCA9548A를 통해 두 개의 DA7280 햅틱 드라이버를 독립적으로 제어합니다.

* 왼쪽 객체: 왼쪽 진동 모터 작동
* 오른쪽 객체: 오른쪽 진동 모터 작동
* 중앙 객체: 양쪽 진동 모터 작동
* 위험 단계가 DANGER인 경우: 양쪽 모터를 동시에 작동

위험 단계에 따라 진동 강도, 지속 시간, 반복 주기를 다르게 설정합니다.

위험 단계	진동 강도	지속 시간	반복 주기
FAR	55	0.08초	1.20초
NEAR	90	0.15초	0.60초
DANGER	127	0.25초	0.30초

※ 위 값은 현재 코드에 설정된 상대 제어값입니다.

4.6 음성 안내

TTS 엔진을 통해 탐지 객체의 종류, 방향 및 위험 수준을 음성으로 안내합니다. 위험 단계가 DANGER로 변경되면 기존 음성 안내를 중단하고 긴급 경고를 우선 전달하도록 구현했습니다.

코드에서는 espeak-ng, espeak, spd-say, festival 중 사용 가능한 음성 엔진을 탐색합니다. 기본 언어 설정은 영어이며, TTS_LANG 값을 변경하여 한국어 안내를 설정할 수 있습니다.

5. 소프트웨어 아키텍처

실시간 영상 처리와 피드백 출력이 서로의 실행을 지연시키지 않도록 스레드를 분리했습니다.

스레드	역할
CameraThread	GStreamer 기반 카메라 영상 획득
DetectorThread	YOLO 추론, 객체 위치 및 위험 단계 판별, 주요 위험 객체 선정
HapticThread	I²C 통신 및 좌·우 DA7280 진동 제어
TTSThread	위험 정보에 따른 음성 안내
main	OpenCV UI 표시 및 전체 스레드 실행·종료 관리

HazardHub를 통해 탐지 스레드에서 선정한 주요 위험 정보를 햅틱 및 음성 스레드에 전달합니다. 각 출력 기능을 별도 스레드로 실행하여 피드백 처리 중에도 영상 추론이 지속될 수 있도록 구성했습니다.

6. 실행 환경 설정

사전 준비

다음 장치와 환경이 필요합니다.

* NVIDIA Jetson Orin Nano
* IMX219 CSI 카메라
* DA7280 햅틱 드라이버 2개 및 진동 액추에이터
* TCA9548A I²C 멀티플렉서
* 스피커 또는 이어폰
* 카메라 및 I²C 장치 연결이 완료된 Jetson 환경

Python 패키지 설치

Jetson에 맞는 PyTorch 및 CUDA 환경을 먼저 구성한 뒤 필요한 패키지를 설치합니다.

pip install opencv-python smbus2 ultralytics

GStreamer, 카메라 드라이버, TTS 엔진은 시스템 환경에 맞게 별도로 준비해야 합니다.

음성 안내에 espeak-ng를 사용할 경우 다음과 같이 설치할 수 있습니다.

sudo apt install espeak-ng

모델 준비

현재 제공된 코드의 기본 모델 경로는 다음과 같습니다.

MODEL_PATH = "yolov8n.pt"

모델 파일을 실행 경로에 준비하거나 MODEL_PATH를 실제 모델 파일 경로로 변경합니다.

하드웨어 설정 확인

실제 장치 구성에 맞게 다음 설정을 확인합니다.

SENSOR_ID = 0
I2C_BUS = 7
TCA9548A_ADDR = 0x70
DA7280_ADDR = 0x4A
LEFT_CHANNEL = 0
RIGHT_CHANNEL = 1

카메라 센서 ID, I²C 버스 번호, 멀티플렉서 채널은 연결 환경에 따라 수정해야 합니다.

실행

메인 Python 파일이 있는 디렉터리에서 실행합니다.

python3 main.py

※ 실제 파일명이 main.py와 다르다면 해당 파일명으로 실행 명령을 변경하세요.

7. 주요 설정값

설정 변수	설명
WIDTH, HEIGHT, FPS	카메라 입력 해상도 및 프레임 속도
MODEL_PATH	YOLO 모델 파일 경로
IMGSZ	YOLO 추론 입력 크기
CONF_THRES	객체 탐지 신뢰도 임계값
LEFT_LIMIT, RIGHT_LIMIT	화면 방향 구분 기준
AREA_NEAR, AREA_DANGER	근접 및 위험 면적 기준
BOTTOM_DANGER	화면 하단 위험 판단 기준
HAPTIC_PATTERN	위험 단계별 진동 제어값
TTS_ENABLED	음성 안내 활성화 여부
TTS_LANG	음성 안내 언어 설정

8. 실험 결과

논문에 보고된 통합 시험 결과는 다음과 같습니다.

* 실내 및 야외 육상 트랙 환경에서 시스템 통합 동작 시험
* 1280×720 해상도, 카메라 30 FPS 설정
* YOLO 추론 입력 크기 640 설정
* 객체 탐지 및 화면 표시를 포함하여 약 28~30 FPS 유지
* 객체 위치에 따른 LEFT, CENTER, RIGHT 방향 판별 확인
* 객체의 상대적 근접도 변화에 따른 위험 단계 전환 확인
* 방향별 햅틱 진동 및 음성 경고 동작 확인
* 복수 객체 탐지 시 Primary Hazard 선정 동작 확인

실험 결과는 논문에 기재된 프로토타입 통합 시험 결과이며, 실제 시각장애인 사용자를 대상으로 한 안전성 및 사용성 검증 결과를 의미하지는 않습니다.

9. 한계점 및 향후 개선 방향

현재 시스템은 단안 카메라 영상의 바운딩 박스 크기와 위치를 이용해 상대적 위험도를 판단합니다. 따라서 실제 장애물까지의 절대 거리를 정밀하게 측정하는 방식은 아닙니다.

향후 다음과 같은 개선이 필요합니다.

* 실제 주행 데이터를 활용한 위험도 임계값 및 가중치 최적화
* 실제 시각장애인 주자를 대상으로 한 사용자 평가
* 트랙 경계선 인식 기능 추가
* 소형 장애물 인식 기능 추가
* 다양한 조명 및 야외 환경에서의 탐지 성능 검증
* 실제 주행 상황에서의 안전성 및 실용성 검증

10. 저장소 구성 예시

현재 제공된 코드 자료를 GitHub에 정리할 때 다음과 같은 구조를 권장합니다.

Track-I/
├── README.md
├── main.py
├── requirements.txt
├── docs/
│   └── paper.pdf
├── assets/
│   ├── system_architecture.png
│   ├── prototype.png
│   └── detection_result.png
└── .gitignore

※ 위 구조는 권장 예시입니다. 실제 저장소에 추가한 파일명과 디렉터리에 맞게 수정하세요.

11. 참고 자료

* NVIDIA Jetson Orin Nano Developer Kit User Guide
* Renesas Electronics, DA7280 Datasheet
* Texas Instruments, TCA9548A Datasheet
* Ultralytics YOLO Documentation
* R. K. Katzschmann, B. Araki, and D. Rus, “Safe Local Navigation for Visually Impaired Users With a Time-of-Flight and Haptic Feedback Device,” IEEE Transactions on Neural Systems and Rehabilitation Engineering, 2018.
* Z. A. Ali, “Design and evaluation of two obstacle detection devices for visually impaired people,” Journal of Engineering Research, 2023.
* Y. Gao et al., “A wearable obstacle avoidance device for visually impaired individuals with cross-modal learning,” Nature Communications, 2025.

12. 구현 버전 참고 사항

논문과 현재 제공된 코드 자료 사이에는 일부 설정 및 명칭 차이가 있습니다. README는 실제 코드의 실행 설정을 우선하여 설명하고, 논문에 보고된 연구 결과는 별도로 구분했습니다.

* 논문 본문: YOLO11n 기반 객체 탐지, LOW/MEDIUM/HIGH 위험 단계
* 제공된 코드: yolov8n.pt 기본 모델 경로, FAR/NEAR/DANGER 위험 단계
* 논문 본문: 신뢰도 임계값 0.35 및 추론 입력 크기 640으로 기술
* 제공된 코드: CONF_THRES = 0.40, IMGSZ = 416으로 설정

실제 GitHub에 최종 코드를 업로드하기 전에 논문에 사용한 버전과 공개할 코드 버전을 확인하고, README의 모델명·임계값·실험 설정을 최종 버전에 맞춰 업데이트하는 것을 권장합니다.

⸻

Project: Track-I
Institution: Hanyang Women’s University, Department of IT Contents Convergence
Project Type: Hanium Dream-up Project
