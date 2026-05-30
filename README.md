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
    -> outputs/generations/{generation_id}.json 저장
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

`status`가 `degraded`이고 `gemini_api_key`가 `false`이면 `GEMINI_API_KEY` 또는 `GOOGLE_API_KEY`를 설정해야 NPC 생성 API를 사용할 수 있습니다. 이 경우 `/api/v1/generate`는 `503 Service Unavailable`을 반환합니다.

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
    "max_dialogue_depth": 3
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

## Google Cloud Run 배포 개요

1. Google Cloud 프로젝트에서 Artifact Registry와 Cloud Run API를 활성화합니다.
2. `GEMINI_API_KEY`를 Secret Manager 또는 Cloud Run 환경 변수로 설정합니다.
3. Docker 이미지를 빌드하고 Artifact Registry에 푸시합니다.
4. Cloud Run 서비스로 배포하고 컨테이너 포트 `8000`을 노출합니다.
5. Docker 이미지의 health check는 `/api/v1/health`를 호출해 컨테이너 상태를 확인합니다.
6. 운영 환경에서는 `outputs/`가 컨테이너 로컬 디스크에 저장되므로 장기 보관이 필요하면 Cloud Storage 연동을 추가합니다.

## XPRIZE 카테고리 추천

추천 카테고리: **Small Business Services**

NPC Simulator는 소규모 게임 제작팀이 NPC 콘텐츠 제작과 검증을 빠르게 제품화하도록 돕는 업무 자동화 서비스에 가깝습니다.

## Gemini/Google Cloud 사용 지점

- Gemini 2.5 Flash: NPC blueprint 생성, Unity C# 코드 생성, self-healing, 보너스 대사 생성
- FastAPI on Google Cloud Run: 서버리스 API 및 대시보드 호스팅
- Google Secret Manager 권장: Gemini API 키 관리
- Artifact Registry 권장: Cloud Run 배포용 컨테이너 이미지 저장
