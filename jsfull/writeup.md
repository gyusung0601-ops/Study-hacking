# POKA CTF 2024 — `js full` (web / XS-Leak) 풀이

> 원본 챌린지 소스: [`challenge/app/index.js`](./challenge/app/index.js)
> 익스플로잇 스캐폴드: [`exploit/`](./exploit)

## 1. 챌린지 개요

Express 서버(포트 30000) + `puppeteer-core` 봇(headless Chrome)으로 구성된
전형적인 **client-side XS-Leak** 문제다. 이름 그대로 "full" — XS-Leak을 막는
보안 헤더가 전부 걸려 있다.

목표: `process.env.FLAG`를 얻는 것. 플래그는 `/flag` 엔드포인트가 내려주는데,
쿼리 `secret`이 서버가 들고 있는 40비트 `secret` 배열과 정확히 일치해야 한다.

```js
app.get('/flag', (req, res) => {
    if (req.query?.secret !== secret.join(""))   // 40자리 "0/1" 문자열
        return res.send('Invalid secret');
    res.send(process.env.FLAG ?? 'pokactf2024{test}');
});
```

즉 **40비트(2^40)를 알아내면 플래그**다. 무작정 때려맞히는 건 불가능하니
`secret`을 "누출"시켜야 한다.

## 2. 상태 기계 이해하기

### 2.1 `secret` 의 생애주기

```js
let secret = Array.from(crypto.randomBytes(40), byte => byte % 2);  // 전역, 40비트
```

`secret`은 **모듈 전역**이다. 그리고 봇이 한 번 방문할 때마다:

```js
const visit = async (url) => {
    secret    = Array.from(crypto.randomBytes(40), byte => byte % 2); // (A) 방문 시작 시 재생성
    bot_token = crypto.randomBytes(32).toString('hex');              //     봇 토큰도 재생성
    ...
    await page.setCookie({ name:'bot_token', value:bot_token, domain:'localhost', httpOnly:true });
    await page.goto(url, { timeout: 1000, waitUntil:'domcontentloaded' });
    await sleep(35000);                                              // (B) 35초 동안 브라우저 유지
    ...
    finally { secret = ...; bot_token = ...; }                       // (C) 방문 종료 시 다시 재생성(무효화)
};
```

따라서 유효한 공격 창은 **봇 방문 1회당 딱 한 번, 약 35초**다. 이 창 안에서
40비트를 전부 누출하고, 그 값이 살아 있는 동안 `/flag`를 때려야 한다.

### 2.2 핵심: `/secret/:index` 는 "파괴적 읽기" 오라클

```js
app.get('/secret/:index', (req, res) => {
    if (!(/^[0123456789]+$/.test(req.params.index ?? ''))) return res.send('Invalid index');
    const index = parseInt(req.params.index ?? '');
    if (index < 0 || index >= secret.length) return res.send('Invalid index');

    if (req.cookies?.bot_token !== bot_token)                         // 봇이 아니면 → 디코이(패리티)
        return res.send(index % 2 ? `<img src='/gosu.webp'>` : 'i wanna gosu');

    secret[index] = crypto.randomInt(2);                             // 봇이면 → 해당 비트를 새 난수로 덮음
    res.send(secret[index] ? `<img src='/gosu.webp'>` : 'i wanna gosu'); // 그리고 "새 값"을 렌더
});
```

두 가지가 결정적이다:

1. **봇 토큰이 없으면 무의미하다.** 일반 방문자(=우리가 직접 보내는 요청, 또는
   봇이 *크로스-사이트 서브리소스*로 보내는 요청)에게는 `index % 2`만 반영한
   가짜 응답을 준다. `secret`과 무관 → 여기서는 아무것도 못 샌다.

2. **봇이 읽으면 그 비트가 "새 난수"로 바뀌고, 바뀐 값이 응답에 인코딩된다.**
   `bit == 1` → `<img src='/gosu.webp'>` (브라우저가 이미지 서브리소스를 **추가로 요청**),
   `bit == 0` → 텍스트(추가 요청 없음).
   읽는 순간 값이 확정되고, 우리가 그 응답(=img인지 text인지)만 관측하면
   **그 비트의 현재 값을 알게 된다.** 이후 다시 읽지 않는 한 값은 그대로 유지된다.

즉 봇으로 `index 0..39`를 각각 **정확히 한 번씩** 읽게 하고, 매번 "img가 떴는지"만
알아내면 40비트 전체를 확정할 수 있다. 그다음 우리가 직접
`GET /flag?secret=<40비트>` 를 치면 된다 (`/flag`는 쿠키가 필요 없다).

**남은 유일한 문제: "봇의 브라우저에서 img 서브리소스가 로드됐는지"를
크로스-오리진으로 어떻게 관측하는가.** 이게 이 문제의 전부이고, 그래서 "full"이다.

## 3. 왜 어려운가 — 걸려 있는 방어들

모든 응답에 다음 헤더가 붙는다(line 50–62):

| 헤더 | 값 | 막는 XS-Leak |
|---|---|---|
| `Content-Security-Policy` | `default-src 'self'; frame-ancestors 'none'` | 외부 리소스/인라인, iframe 임베드 |
| `X-Frame-Options` | `deny` | iframe 임베드(→ `frame` 개수 세기 leak 차단) |
| `Cross-Origin-Opener-Policy` | `same-origin` | `window.open` 후 opener/팝업 참조 단절, `window.length` leak |
| `Cross-Origin-Embedder-Policy` | `require-corp` | credentialless 로딩 강제 |
| `Cross-Origin-Resource-Policy` | `same-origin` | 크로스-오리진 서브리소스 응답 수신(이미지 크기 leak 등) |
| `X-Content-Type-Options` | `nosniff` | MIME 혼동 leak |
| `Document-Policy` | `force-load-at-top` | scroll-to-text-fragment leak |
| `Referrer-Policy` | `no-referrer` | referrer 기반 leak |
| `Cache-Control` | `no-store` | 캐시 프로빙 leak |

게다가 봇 실행 플래그에 **`--js-flags=--noexpose_wasm,--jitless`** 가 있다(line 22).
WASM/JIT를 꺼서 고해상도 타이머·Spectre류 CPU 타이밍 사이드채널을 봉쇄한다.
→ **정밀 타이머에 의존하는 leak은 못 쓴다.**

또한 쿠키 `bot_token`은 `sameSite`가 지정되지 않았다 → 크롬 기본 **Lax**.
따라서:

- **크로스-사이트 서브리소스**(`fetch`/`img`/`XHR`)로 `localhost:30000/secret/i`를
  때리면 **쿠키가 안 붙는다** → 디코이 분기 → 무의미.
- **탑레벨 GET 내비게이션**(주소창 이동/팝업 열기)만이 Lax 쿠키를 실어 보낸다.

그리고 CSP가 `'self'`라 봇이 방문한 challenge 페이지 안에서 우리 스크립트를
실행시킬 HTML 인젝션 싱크도 없다(모든 응답이 고정 문자열/이스케이프됨) → **XSS 불가**.

정리하면, **봇으로 하여금 `/secret/i` 로 "탑레벨 내비게이션"을 시키고(쿠키 실림),
그때 발생하는 `gosu.webp` 서브리소스 요청의 유무를, 정밀 타이머 없이,
크로스-오리진으로 감지**해야 한다.

## 4. 남는 누출 채널 — Connection-Pool(소켓 풀) 사이드채널

COOP/COEP/CORP/CSP/XFO는 전부 **DOM/리소스 수준**의 크로스-오리진 관측을 막는다.
하지만 브라우저의 **전역 소켓 풀**은 오리진과 무관한 공용 자원이다. 이 경합(contention)은
정밀 타이머 없이도 "이벤트가 몇 개 도착했나" 수준의 거친 타이밍으로 읽을 수 있어
`--jitless`/`--noexpose_wasm` 환경에서도 살아남는다. (xsleaks.dev "Connection Pool" 참고)

원리:

- 크롬은 **호스트당 6개**, **전역 ~256개** 동시 소켓으로 제한된다.
- 공격자 페이지에서 우리 서버로 **끝나지 않는 요청(hang)** 을 다수 띄워 전역 풀을
  거의 소진시키고, 남은 슬롯 수를 통제한다.
- 그 상태에서 팝업을 `/secret/i`로 **탑레벨 이동**시킨다.
  - `bit==1` → challenge가 HTML 소켓 1개 + `gosu.webp` 소켓 1개, **총 2개** 사용
  - `bit==0` → HTML 소켓 **1개**만 사용
- 동시에 공격자 페이지가 "빈 슬롯이 나야만 진행되는 프로브 요청"을 띄우고
  **완료까지 걸린 상대적 시간/순서**를 측정한다. 타깃이 소켓을 1개 더
  쓰면(=bit 1) 프로브가 더 늦게 풀린다 → **비트 1/0 판별**.

이렇게 40비트를 순차로 긁는다. 공격자 페이지(opener)는 계속 살아 있으므로
(COOP는 우리가 *우리 자신의* 소켓을 재는 걸 막지 못한다) 팝업을 열고·측정하고·닫는
루프를 35초 창 안에서 40회 반복한다(비트당 ~0.8초).

> ⚠️ 이 채널은 본질적으로 **환경 의존적**이다(소켓 수 튜닝, 팝업 허용 여부, 봇 머신
> 성능). 아래 스캐폴드는 파라미터화되어 있으며, 실제 인스턴스에서 소켓 수/딜레이를
> 몇 번 조정해야 안정적으로 40/40이 나온다.

### 대안 채널
`window.open`이 봇 환경에서 사용자 제스처 없이 막힐 경우, 각 비트마다 `/bot`에
`http://localhost:30000/secret/i` 를 **개별 report** 하고(봇이 그 URL로 탑레벨 이동 →
쿠키 실림 → img/text 렌더), 그동안 공격자 서버가 **자기 소켓 풀 경합**으로 img 요청
유무를 재는 방식으로 분해할 수도 있다. 다만 방문마다 `secret`이 재생성되므로(2.1의 A),
이 방식은 "비트별 개별 방문 → 개별 판별 → 마지막에 40개를 하나의 방문 안에서 다시
확정" 하는 조율이 필요해 더 번거롭다. 스캐폴드는 **한 방문 안에서 팝업 40회** 방식을
기본으로 한다.

## 5. 익스플로잇 절차 (요약)

1. 공격자 서버(`exploit/server.js`)를 봇이 접근 가능한 호스트에 띄운다.
   - `/` : 얇은 공격 페이지(1초 안에 domcontentloaded — line 34의 `timeout:1000` 때문)
   - `/hang` : 소켓을 붙잡아 두는 엔드포인트(풀 소진용)
   - `/probe` : 타이밍 프로브 대상
   - `/leak?i=..&b=..` : 공격 페이지가 판별한 비트를 보고
   - 40비트가 모이면 서버가 즉시 `GET http://CHALLENGE/flag?secret=<bits>` 호출
2. challenge의 `/bot`에 `http://<공격자서버>/?target=http://localhost:30000` 를 report.
3. 봇이 공격 페이지를 열고, 페이지가 팝업으로 `/secret/0..39`를 순차 탑레벨 방문하며
   각 비트를 소켓-풀 타이밍으로 판별 → `/leak`로 전송.
4. 서버가 40비트 조립 → `/flag` 호출 → **플래그 획득**.

자세한 실행법은 [`exploit/README.md`](./exploit/README.md).

## 6. 교훈 / 방어

- **파괴적 읽기 오라클을 클라이언트가 관측 가능한 형태(서브리소스 유무)로 인코딩하지 말 것.**
  `img` vs 텍스트라는 차이가 곧 1비트 누출 채널이 됐다.
- XS-Leak 방어 헤더를 "풀세트"로 걸어도 **소켓 풀 같은 전역 브라우저 자원 경합**은
  남는다. 근본적으로 민감 상태를 봇의 인증 컨텍스트에서 **관측 가능한 부수효과 없이**
  다뤄야 한다(예: 응답을 상수 시간·상수 리소스로 만들기).
- 인증 게이팅(`bot_token`)은 잘 돼 있었지만, **관측 가능한 응답 차이**가 게이트를 우회했다.

## 참고

- xsleaks.dev — [Connection Pool](https://xsleaks.dev/docs/attacks/timing_attacks/connection-pool/)
- 이 문제는 실제 인스턴스가 살아 있어야 플래그(`process.env.FLAG`)를 얻을 수 있다.
  소스의 기본값은 `pokactf2024{test}` (Dockerfile) / `pokactf2024{test}` (index.js fallback)로,
  **실제 플래그가 아니다.** 실 배포 인스턴스에 위 익스플로잇을 돌려야 진짜 플래그가 나온다.
