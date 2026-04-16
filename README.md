
1. 이 저장소(프로젝트 루트, `docker-compose.yml`이 있는 디렉터리)로 이동합니다.

   ```bash
   cd /path/to/fin-us
   ```

2. api키를 사용하기 위해 환경 파일을 만듭니다.

   ```bash
   cp fin-us/backend/.env.example fin-us/backend/.env
   ```

   OpenAI/Anthropic를 쓸 때는 `fin-us/backend/.env`에 키를 입력합니다.

3. 도커 이미지를 빌드합니다.

   ```bash
   bash scripts/run_stack.sh
   ```
4. 브라우저에서 프론트를 엽니다.

   - 프론트: http://localhost:5173
