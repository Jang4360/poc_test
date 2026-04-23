# 현재 스프린트 서브플랜

이 디렉터리는 `.ai/PLANS/current-sprint.md`에 연결되는 워크스트림 단위 계획 파일을 보관한다.

## 규칙

- `current-sprint.md`는 스프린트 인덱스이자 상위 체크리스트다.
- 의미 있는 워크스트림마다 이 디렉터리에 별도 마크다운 파일을 둔다.
- 하나의 거대한 실행 계획보다 도메인, API, UI, 배치, 운영 관심사 단위로 나누는 편을 우선한다.
- 모든 서브플랜은 `Success Criteria`, `Implementation Plan`, `Validation Plan` 섹션을 명시적으로 포함해야 한다.
- `scripts/scaffold-plan.sh`로 초안을 만든 뒤 리뷰를 거쳐 세부 내용을 다듬는다.
- 기존 명세 기반 요청이면 `Source Inputs`에 참조 문서를 기록한다.
- 명령 기반 또는 변경 기반 요청이면 변경 요지를 다시 서술하고 영향 영역을 기준으로 워크스트림을 나눈다.

## 권장 파일명

- `auth-api.md`
- `billing-ui.md`
- `admin-reporting.md`
- `release-safety.md`
- `docs-alignment.md`
