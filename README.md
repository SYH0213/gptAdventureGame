# GPT 기반 인터랙티브 텍스트 어드벤처 게임

이 프로젝트는 Flask와 Google Gemini API를 사용하여 사용자가 직접 스토리를 입력하고, 그에 따라 게임 마스터가 상황을 전개하며 플레이어의 상태를 관리하는 인터랙티브 텍스트 어드벤처 게임입니다.

## 주요 기능

-   **사용자 정의 게임 설정**: 플레이어가 게임 시작 시 게임 마스터(GM)의 성격, 게임 난이도, 장르, 플레이어 역할, 게임 목표 등을 직접 설정할 수 있습니다.
-   **Gemini 기반 게임 마스터**: Google Gemini (gemini-2.5-flash 모델)가 게임 마스터 역할을 수행하며, 플레이어의 행동과 설정에 따라 상황을 서술하고 선택지를 제시합니다.
-   **효율적인 AI 대화 관리**: `ChatSession`을 사용하여 게임 설정 및 규칙을 초기에 한 번만 전달하고, 이후 대화는 효율적으로 관리하여 토큰 사용량을 최적화하고 AI의 일관성을 높였습니다.
-   **플레이어 상태 관리**: 위치, 체력, 공격력, 인벤토리, 레벨, 경험치, 목표 등 플레이어의 다양한 스탯을 관리하고 웹 UI에 표시합니다.
-   **게임 저장 및 불러오기**: 현재 게임 상태(플레이어 스탯 및 AI 대화 기록)를 JSON 파일로 다운로드하여 저장하고, 나중에 해당 파일을 업로드하여 게임을 이어서 플레이할 수 있습니다.
-   **게임 목표 및 종료**: 게임 시작 시 설정된 목표를 달성하면 게임이 종료되고 마무리 멘트가 나옵니다.
-   **웹 인터페이스**: 간단한 HTML/CSS/JavaScript 기반의 웹 UI를 통해 게임을 플레이할 수 있습니다.
-   **환경 변수 관리**: `.env` 파일을 통해 API 키를 안전하게 관리합니다.
-   **Docker 지원**: Cloud Run과 같은 컨테이너 환경에 배포할 수 있도록 `Dockerfile`을 제공합니다.

## 프로젝트 구조

```
gptAdventureGame/
├── app.py              # Flask 애플리케이션의 핵심 로직
├── Dockerfile          # Cloud Run 배포용 Dockerfile
├── requirements.txt    # Python 패키지 의존성
├── .env                # 환경 변수 (예: GOOGLE_API_KEY)
├── game_rules2.md      # 게임 마스터의 규칙 및 지침
└── templates/
    └── index.html      # 게임 플레이를 위한 웹 UI
```

## 시작하기

### 1. 프로젝트 클론

```bash
git clone [YOUR_REPOSITORY_URL]
cd gptAdventureGame
```

### 2. Python 가상 환경 설정

프로젝트 루트 디렉토리에서 가상 환경을 생성하고 활성화합니다.

```bash
python -m venv gemini
# Windows
.\gemini\Scripts\activate
# macOS/Linux
source gemini/bin/activate
```

### 3. 의존성 설치

활성화된 가상 환경에서 필요한 Python 패키지를 설치합니다.

```bash
pip install -r requirements.txt
```

### 4. 환경 변수 설정

프로젝트 루트 디렉토리(`.env` 파일이 있는 곳)에 `.env` 파일을 생성하고, Google Gemini API 키를 다음과 같이 추가합니다.

```
GOOGLE_API_KEY=YOUR_API_KEY
```

`YOUR_API_KEY` 부분에 [Google AI Studio](https://aistudio.google.com/app/apikey) 또는 [Google Cloud Console](https://console.cloud.google.com/)에서 발급받은 실제 Gemini API 키를 입력하세요.

### 5. 게임 규칙 설정

`game_rules2.md` 파일을 열어 게임 마스터가 따를 규칙과 지침을 확인하거나 수정할 수 있습니다. 이 파일의 내용은 게임 진행에 중요한 영향을 미칩니다.

### 6. 애플리케이션 실행 (로컬)

가상 환경이 활성화된 상태에서 다음 명령어를 실행하여 Flask 애플리케이션을 시작합니다.

```bash
python app.py
```

애플리케이션이 시작되면 웹 브라우저에서 `http://127.0.0.1:8080` (또는 콘솔에 표시되는 주소)으로 접속하여 게임을 플레이할 수 있습니다.

## Cloud Run 배포 방법

1.  **Google Cloud SDK 설치 및 인증**:
    아직 설치하지 않았다면 [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)를 설치하고, `gcloud auth login` 명령어를 사용하여 인증합니다.

2.  **Google Cloud 프로젝트 설정**:
    배포할 Google Cloud 프로젝트를 설정합니다.
    ```bash
    gcloud config set project YOUR_PROJECT_ID
    ```
    `YOUR_PROJECT_ID` 부분에 실제 Google Cloud 프로젝트 ID를 입력하세요.

3.  **Cloud Build를 사용하여 Docker 이미지 빌드 및 Container Registry에 푸시**:
    프로젝트 루트 디렉토리에서 다음 명령어를 실행합니다.
    ```bash
    gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/gpt-adventure-game
    ```
    `YOUR_PROJECT_ID`를 실제 프로젝트 ID로 변경하세요.

4.  **Cloud Run에 서비스 배포**:
    이미지 빌드가 완료되면 다음 명령어를 사용하여 Cloud Run에 서비스를 배포합니다.
    ```bash
    gcloud run deploy gpt-adventure-game --image gcr.io/YOUR_PROJECT_ID/gpt-adventure-game --platform managed --region YOUR_REGION --allow-unauthenticated --set-env-vars GOOGLE_API_KEY=YOUR_API_KEY
    ```
    -   `YOUR_PROJECT_ID`: 실제 Google Cloud 프로젝트 ID
    -   `YOUR_REGION`: 배포할 리전 (예: `asia-northeast3` 또는 `us-central1`)
    -   `GOOGLE_API_KEY`: 실제 Google Gemini API 키

    배포가 완료되면 Cloud Run 서비스의 URL이 출력됩니다. 해당 URL로 접속하여 게임을 플레이할 수 있습니다.
