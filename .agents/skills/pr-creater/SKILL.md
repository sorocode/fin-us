---
name: pr-creator
description: "PR을 생성합니다. 'PR 올려줘', 'PR 만들어줘'라고 하면 발동됩니다."
---

# PR Creator Skill

## 필수 규칙

PR 생성 시 반드시 .github/ 디렉토리의 PR 템플릿을 사용합니다.

## 워크플로

### 1. 템플릿 로드

```bash
# 템플릿 파일 확인 및 로드
ls .github/
cat .github/PULL_REQUEST_TEMPLATE.md
```

### 2. 현재 변경사항 파악

```bash
git log main..HEAD --oneline
git diff main..HEAD
```

### 3. 템플릿 기반으로 본문 작성

로드한 템플릿 형식을 그대로 유지하면서
현재 변경사항을 분석해 내용을 채웁니다.
템플릿 구조(섹션, 체크리스트 등)를 절대 변경하지 않습니다.

### 4. 사용자 확인

생성할 PR 제목과 본문을 먼저 보여주고 확인받습니다.
확인 없이 바로 올리지 않습니다.

### 5. PR 생성

```bash
gh pr create --title "<제목>" --body "<본문>" --base main
```
