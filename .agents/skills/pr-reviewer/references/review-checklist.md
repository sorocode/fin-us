# .agents/skills/pr-reviewer/references/review-checklist.md

# PR 리뷰 체크리스트

## 보안

- [ ] 사용자 입력값 검증 및 이스케이프 처리
- [ ] 인증/인가 로직 올바른지 확인
- [ ] 민감 정보(API 키, 패스워드) 하드코딩 여부
- [ ] SQL Injection, XSS, CSRF 취약점
- [ ] 의존성 패키지 취약점 (npm audit / pip audit)

## 성능

- [ ] N+1 쿼리 패턴
- [ ] 불필요한 전체 조회 (SELECT \*)
- [ ] 루프 내 동기 I/O 또는 API 호출
- [ ] 캐싱 기회 누락

## 안정성

- [ ] 예외 처리 누락 (try/catch, error handling)
- [ ] null/undefined 체크
- [ ] 경계값 및 엣지케이스 처리
- [ ] 타임아웃, 재시도 로직

## 테스트

- [ ] 새 로직에 대한 테스트 존재 여부
- [ ] 엣지케이스 테스트
- [ ] 기존 테스트 모두 통과 여부

## 코드 품질

- [ ] 함수/변수 네이밍이 의도를 명확히 전달하는지
- [ ] 함수가 단일 책임 원칙(SRP) 따르는지
- [ ] 매직 넘버/문자열 상수화
- [ ] 중복 코드 제거
