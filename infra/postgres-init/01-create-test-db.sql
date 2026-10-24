-- 컨테이너를 처음 만들 때(볼륨이 비어 있을 때)만 실행된다.
-- 테스트가 개발 DB를 지우지 않도록 테스트 전용 DB를 따로 둔다 (backend/tests/conftest.py).
CREATE DATABASE flowdeck_test;
