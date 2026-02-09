# Vibe Digest

Jina AI와 GPT-4o-mini를 기반으로 한 미니멀한 뉴스레터/블로그 요약 서비스입니다.
https://vibe-digest-pi.vercel.app/

## 프로젝트 구조 (Project Structure)

- `frontend/`: Next.js 애플리케이션 (UI 담당)
- `backend/`: Python FastAPI 애플리케이션 (로직 담당)
- `api/`: Vercel Serverless Function 진입점
- `vercel.json`: Vercel 배포 라우팅 설정값

## 준비물 (Prerequisites)

- Antigravity / 터미널 환경
- Node.js & npm
- Python 3.12 이상
- OpenAI API 키
- Vercel 계정

## 로컬 실행 방법 (Setup & Run Locally)

### 1. 백엔드 (Backend) 설정

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

`backend/` 폴더 안에 `.env` 파일을 생성하고 OpenAI 키를 입력하세요:
```
OPENAI_API_KEY=sk-...
JINA_API_KEY=... (선택사항)
```

백엔드 서버 실행:
```bash
uvicorn main:app --reload --port 8000
```

### 2. 프론트엔드 (Frontend) 설정

새로운 터미널 창을 열고 실행하세요:
```bash
cd frontend
npm install
npm run dev
```

프론트엔드는 `http://localhost:3000`에서 실행됩니다.
참고: 프론트엔드는 `/api/summarize`로 요청을 보냅니다. 로컬에서 테스트할 때는 Next.js 프록시 설정이 필요하거나, 직접 `http://localhost:8000/api/summarize`를 호출하도록 코드를 수정해야 할 수도 있습니다.
*하지만 Vercel에 배포하면 `vercel.json` 설정 덕분에 자동으로 연결됩니다.*

## Vercel 배포 방법 (Deployment)

1. 이 저장소(Repository)를 GitHub에 푸시(Push)합니다.
2. Vercel에서 프로젝트를 가져오기(Import) 합니다.
3. **환경 변수 (Environment Variables)**: Vercel 프로젝트 설정에서 `OPENAI_API_KEY`를 추가합니다.
4. **Root Directory**: `.` (프로젝트 루트)로 설정합니다.
5. **Framework Preset**: Next.js가 자동으로 감지될 것입니다.
   *참고: Next.js가 `frontend/` 폴더 안에 있으므로, Vercel이 자동으로 감지하지 못할 경우 Build Command를 `cd frontend && npm install && npm run build`, Output Directory를 `frontend/.next`로 설정해야 할 수 있습니다.*
   
   *또는 더 간단한 배포 방법:*
   루트 경로에서 다음 명령어를 실행하세요:
   ```bash
   vercel
   ```

## 디자인 (Design)
- 메인 컬러: 소프트 그레이 (#F5F5F5)
- 폰트: 산세리프 (Geist/Inter 기본값)
- UI: 미니멀한 카드 레이아웃
