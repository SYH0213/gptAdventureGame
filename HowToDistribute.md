### 프로젝트 실행 방법

1.  **필요한 패키지 설치**:
    프로젝트 루트 디렉토리에서 다음 명령어를 실행하여 필요한 Python 패키지를 설치합니다.
    ```bash
    pip install -r requirements.txt
    ```

2.  **Google API Key 설정**:
    프로젝트 루트 디렉토리에 `.env` 파일을 생성하고, 다음과 같이 `GOOGLE_API_KEY`를 설정합니다.
    ```
    GOOGLE_API_KEY=YOUR_API_KEY
    ```
    `YOUR_API_KEY` 부분에 실제 Google API 키를 입력하세요.

3.  **애플리케이션 실행**:
    다음 명령어를 실행하여 Flask 애플리케이션을 시작합니다.
    ```bash
    python app.py
    ```
    애플리케이션이 시작되면 웹 브라우저에서 `http://127.0.0.1:8080` (또는 콘솔에 표시되는 주소)으로 접속하여 게임을 플레이할 수 있습니다.

---

### Cloud Run 배포 방법

1.  **Google Cloud SDK 설치 및 인증**:
    아직 설치하지 않았다면 Google Cloud SDK를 설치하고, `gcloud auth login` 명령어를 사용하여 인증합니다.

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
    -   `YOUR_API_KEY`: 실제 Google API 키

    배포가 완료되면 Cloud Run 서비스의 URL이 출력됩니다. 해당 URL로 접속하여 게임을 플레이할 수 있습니다.
