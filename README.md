# NPC Simulator

Gemini 기반 멀티 에이전트가 게임 NPC 설계서, Unity C# FSM 컨트롤러, QA 리포트, 보너스 대사를 생성하고 저장하는 제품형 MVP입니다.

## 대상 고객

인디 게임 스튜디오, 소규모 콘텐츠 제작팀, Unity 프로토타이핑 팀처럼 반복적인 NPC 설계와 구현 검증에 많은 시간을 쓰는 소규모 게임 개발 조직을 대상으로 합니다.

## 핵심 문제와 해결

NPC 제작은 기획 문서, 대화 트리, 런타임 코드, QA 검증이 분리되어 있어 작은 변경도 반복 비용이 큽니다. NPC Simulator는 하나의 컨셉 입력에서 구조화된 JSON blueprint, Unity용 C# FSM 코드, QA 리포트, 저장 가능한 generation bundle을 한 번에 생성해 반복 제작 시간을 줄입니다.

## 주요 기능

- Gemini 2.5 Flash 기반 NPC design agent
- Unity C# FSM controller를 생성하는 developer agent
- schema, dialogue tree, Unity code를 확인하는 QA agent
- self-healing loop를 통한 코드 재생성
- `generation_id` 기반 결과 저장 및 조회 API
- 모바일 companion UI를 고려한 컨셉 입력, 요약 확인, 출력 접힘 보기
- 대시보드에서 generation history 조회, blueprint, C# code, QA report, full bundle 다운로드
- job 기반 비동기 생성 API와 단계별 진행 상태 조회
- QA 요약, Unity C# 파일명/클래스명 메타데이터 제공
- 사용자 Gemini API 키를 저장하지 않고 1회 job에만 사용하는 비용 방어 모드
- Full bundle JSON 다운로드 및 업로드 복원 중심의 서버 저장 최소화 흐름
- Google Cloud Run 배포를 고려한 FastAPI 서버와 Dockerfile

## 아키텍처

```text
Browser dashboard
  -> FastAPI /api/v1/generation-jobs
    -> Design Agent: Gemini blueprint JSON 생성
    -> Python json.loads + Pydantic blueprint 검증
    -> Developer Agent: Unity C# FSM 생성
    -> QA Agent: schema/dialogue/code readiness 평가
    -> Self-Healing Agent: QA 실패 시 코드 보정
    -> Bulk Generator: 보너스 대사 생성
    -> Full bundle JSON 다운로드
    -> local dev에서는 outputs/generations/{generation_id}.json 임시 저장 가능
```

## 로컬 실행법

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY="YOUR_API_KEY"
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

환경 변수 예시는 `.env.example`에 있습니다. 실제 비밀 값은 `.env`처럼 git에 포함되지 않는 파일이나 배포 환경 변수로 관리하세요. 앱은 시작 시 프로젝트 루트의 `.env`를 자동으로 읽되, 이미 설정된 환경 변수는 덮어쓰지 않습니다.

브라우저에서 `http://127.0.0.1:8000`을 열면 대시보드를 사용할 수 있습니다.

서버와 필수 설정 상태는 health endpoint로 확인할 수 있습니다.

```bash
curl http://127.0.0.1:8000/api/v1/health
```

`status`가 `degraded`이고 `gemini_api_key`가 `false`이면 서버 데모 키가 없다는 뜻입니다. 대시보드에서 사용자 Gemini API 키를 입력하거나 서버에 `GEMINI_API_KEY` 또는 `GOOGLE_API_KEY`를 설정해야 NPC 생성 API를 사용할 수 있습니다.

## 운영 환경 변수

```bash
GEMINI_API_KEY=optional_demo_key
GOOGLE_API_KEY=optional_demo_key
MAX_ACTIVE_JOBS=2
MAX_HEALING_ATTEMPTS=3
BONUS_DIALOGUE_COUNT=10
PERSIST_GENERATIONS=true
CORS_ORIGINS=*
```

배포 공개 모드에서는 비용 방어를 위해 `PERSIST_GENERATIONS=false`, `MAX_ACTIVE_JOBS=6`, `CORS_ORIGINS=https://your-domain.example`처럼 환경별로 조정하세요. 사용자 API 키는 요청 본문에만 포함되며 response, log, saved bundle에는 저장하지 않습니다.

## 테스트

외부 Gemini 호출 없이 핵심 검증 로직, 저장/조회 흐름, 설정 오류 응답을 확인하는 회귀 테스트를 실행할 수 있습니다.

```bash
python -m unittest discover -s tests -v
```

상세 테스트 결과, 발견된 문제, 적용한 개선, 남은 live Gemini 검증 절차는 `TEST_REPORT.md`에 정리되어 있습니다.

## API 예시

NPC 생성:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "world_setting": {
      "genre": "RPG",
      "lore_summary": "Distopian Incinerator Zone"
    },
    "user_prompt": "폐쇄된 기록 보관소를 지키는 기억 수집가",
    "max_dialogue_depth": 3
  }'
```

응답에는 기존 `blueprint`, `code`, `qa_report`, `self_healing`, `bonus_assets`, `logs`와 함께 `generation_id`, `created_at`, `metrics`, `summary`, `unity_metadata`가 포함됩니다.

비동기 생성 job 시작:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/generation-jobs \
  -H "Content-Type: application/json" \
  -d '{
    "world_setting": {
      "genre": "RPG",
      "lore_summary": "Distopian Incinerator Zone"
    },
    "user_prompt": "폐쇄된 기록 보관소를 지키는 기억 수집가",
    "max_dialogue_depth": 3,
    "client_api_key": "USER_GEMINI_API_KEY_OPTIONAL"
  }'
```

job 상태 조회:

```bash
curl http://127.0.0.1:8000/api/v1/generation-jobs/{job_id}
```

저장된 결과 목록:

```bash
curl http://127.0.0.1:8000/api/v1/generations
```

특정 결과 조회:

```bash
curl http://127.0.0.1:8000/api/v1/generations/{generation_id}
```

## Docker / Cloud Run 배포 개요

1. Google Cloud 프로젝트에서 Artifact Registry와 Cloud Run API를 활성화합니다.
2. 공개 비용 방어를 위해 기본은 사용자 API 키 입력 방식으로 운영합니다.
3. Docker 이미지를 빌드하고 Artifact Registry에 푸시합니다.
4. Cloud Run 서비스로 배포하고 컨테이너 포트 `8080`을 노출합니다.
5. Docker 이미지의 health check는 `/api/v1/health`를 호출해 컨테이너 상태를 확인합니다.
6. 운영 환경에서는 서버 저장을 장기 보관으로 보지 말고 Full bundle JSON 다운로드를 기본 저장 방식으로 둡니다.

로컬 Docker 실행:

```bash
docker build -t npc-simulator .
docker run --rm -p 8080:8080 -e PORT=8080 -e PERSIST_GENERATIONS=false npc-simulator
```

Cloud Run 배포 예시:

```bash
gcloud run deploy npc-simulator \
  --image REGION-docker.pkg.dev/PROJECT/REPOSITORY/npc-simulator:latest \
  --region REGION \
  --allow-unauthenticated \
  --port 8080 \
  --timeout 300 \
  --concurrency 6 \
  --max-instances 1 \
  --set-env-vars PERSIST_GENERATIONS=false,MAX_ACTIVE_JOBS=6,MAX_HEALING_ATTEMPTS=3,BONUS_DIALOGUE_COUNT=10
```

## Cloudflare 도입 단계

초기 공개는 Cloud Run의 `*.run.app` URL만으로 충분합니다. 외부 브랜딩 단계에서 도메인을 구매해 Cloudflare DNS에 연결하고, 이후 필요하면 `app.example.com`은 Cloudflare Pages, `api.example.com`은 Cloud Run으로 분리합니다. 공개 전에는 `CORS_ORIGINS`를 실제 앱 도메인으로 제한하세요.

## XPRIZE 카테고리 추천

추천 카테고리: **Small Business Services**

NPC Simulator는 소규모 게임 제작팀이 NPC 콘텐츠 제작과 검증을 빠르게 제품화하도록 돕는 업무 자동화 서비스에 가깝습니다.

## Gemini/Google Cloud 사용 지점

- Gemini 2.5 Flash: NPC blueprint 생성, Unity C# 코드 생성, self-healing, 보너스 대사 생성
- FastAPI on Google Cloud Run: 서버리스 API 및 대시보드 호스팅
- Google Secret Manager 권장: Gemini API 키 관리
- Artifact Registry 권장: Cloud Run 배포용 컨테이너 이미지 저장
