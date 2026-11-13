# 🏃‍♂️ TRACK-I: 시각장애인 마라토너를 위한 온디바이스 AI 스마트 벨트

(On-Device Vision AI and Multi-Sensory Feedback-Based Smart Belt System for Visually Impaired Running Assistance)

## 📌 프로젝트 소개 (Introduction)

**TRACK-I**는 시각장애인 마라토너가 가이드 러너의 물리적 연결(테더)과 주변 소음으로 인해 겪는 주행 리듬의 제약 및 정보 전달의 한계를 보완하기 위해 개발된 **스마트 웨어러블 시스템**입니다.

사용자의 전방 영상을 실시간으로 분석하여 전방의 사람(타 주자)을 탐지하고, 객체의 **상대적 위험도를 판단**하여 좌우 독립 햅틱(진동)과 TTS 음성으로 위험 정보를 직관적으로 전달합니다.

### 💡 주요 차별점

* **단순 탐지가 아닌 위험 판단 (Primary Hazard):** 여러 사람이 동시에 탐지될 경우, 바운딩 박스의 면적과 하단 위치를 기반으로 가중치를 계산하여 **가장 충돌 위험이 높은 최우선 객체(Primary Hazard) 단 하나만**을 선별하여 알림을 제공합니다. (정보 과부하 방지)
* **온디바이스 AI (On-Device AI):** 외부 서버 통신 없이 NVIDIA Jetson Orin Nano 내부에서 실시간(약 28~30 FPS) 처리됩니다.
* **다감각 피드백 (Multi-Sensory Feedback):** 대회 현장의 소음을 고려하여, 시각적 위험을 촉각(진동의 방향 및 강도)과 청각(방향 및 위험도 음성)으로 동시에 변환합니다.

## 📂 파일 구조 (Repository Structure)

```text
📦 track-i
 ┣ 📂 assest
 ┃ ┣ 📜 Track-I 발표자료.pdf (최종 졸업작품 발표자료)
 ┃ ┗ 📜 TrackI_Hanium_ACK2026_Paper.pdf (학술대회 게재 논문)
 ┣ 📜 .gitignore
 ┣ 📜 README.md
 ┗ 📜 track_i.py (메인 실행 스크립트)
```

## ⚙️ 하드웨어 구성 (Hardware Requirements)

TRACK-I는 시각장애인이 직접 착용할 수 있는 힙색(벨트) 형태로 통합되어 있습니다.

| 구분 | 부품 / 모델명 | 주요 기능 |
| :--- | :--- | :--- |
| **연산부** | NVIDIA Jetson Orin Nano | 온디바이스 AI 추론 및 전체 시스템 제어 |
| **영상 입력** | IMX219 광각 CSI 카메라 | 전방 주행 영상 실시간 획득 |
| **햅틱 출력** | DA7280 x 2 (좌/우) | 방향 및 위험도에 따른 차등 진동 피드백 |
| **통신 제어** | TCA9548A (I2C 멀티플렉서)| 동일 I2C 주소를 가진 햅틱 모터 2개의 독립 제어 |
| **음성 출력** | 스피커 또는 이어폰 | 방향 및 위험도 TTS 음성 경고 출력 |

## 🧠 소프트웨어 및 알고리즘 (Software Architecture)

### 1. YOLOv8n 기반 객체 탐지
* 모델: Ultralytics **YOLOv8n** (Person 클래스 중심 탐지)
* 입력 크기: 640
* 신뢰도(Confidence) 임계값: 0.35 이상

### 2. 상대적 위험도 산출 (Relative Risk Assessment)
단안 카메라의 한계를 극복하기 위해 영상 내 정보를 활용하여 위험도를 계산합니다.
* **방향(Direction):** 객체의 X 좌표 중심점 기준 `LEFT`, `CENTER`, `RIGHT` 판별
* **위험도(Risk Level):** 객체 바운딩 박스의 면적 비율(A)과 하단 위치 비율(P)을 분석하여 `HIGH`, `MEDIUM`, `LOW`로 분류

### 3. 멀티스레딩 파이프라인 (Multi-threading)
* 메인 스레드는 영상 획득 및 YOLOv8n 추론만 담당하여 병목현상을 최소화합니다.
* 햅틱(Haptic) 제어와 음성(TTS) 제어는 각각 독립된 스레드에서 병렬 처리되어 시스템 지연(Blocking)을 방지합니다.

## 🚀 설치 및 실행 방법 (Installation & Usage)

### 환경 설정 (Prerequisites)
* JetPack 6.x / Ubuntu 22.04 (Jetson Orin Nano)
* Python 3.12.3
* PyTorch 2.12.0 / CUDA 13.2

### 1. Repository 클론
```bash
git clone https://github.com/YourUsername/track-i.git
cd track-i
```

### 2. 패키지 설치
*(요구 패키지: ultralytics, opencv-python, numpy, smbus2 등 환경에 맞게 설치)*
```bash
pip install ultralytics opencv-python numpy smbus2
```

### 3. 시스템 실행
```bash
# I2C 권한 확인 및 활성화 후 실행
python track_i.py
```

## 👥 팀원 (Team TRACK-I)

* **정서윤 (팀장)**: 하드웨어 기초 설계, 개발 환경 구성, 시스템 통합 및 디버깅
* **김소윤**: AI 개발, YOLOv8n 객체 탐지 구현, 햅틱 제어 알고리즘 구현
* **김예선**: 소프트웨어 기획, 카메라 I/O 파이프라인 구축, TTS 음성 시스템 구현

## 🏆 성과 및 참고 자료 (Achievements & References)

* **관련 자료**:
  * [Track-I 최종 발표자료 보기](./assest/Track-I/20발표자료.pdf)
  * [ACK 2026 학술대회 게재 논문 보기](./assest/TrackI_Hanium_ACK2026_Paper.pdf)
* **수상 내역**:
  * 한이음 드림업 지원 사업 장려상
  * 교내 2026 도전 Start UP 리그 입선

## 📝 License

This project is licensed under the MIT License.
