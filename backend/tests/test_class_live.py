"""명세 4.12 5-4 강의실 수업 진행·공지/숙제·원장 강의실(class_routes.py, org_routes.py).

체험 세상(5학년 A반: 담당 김선생님 t1, 학생 지우 s1·민준 s2·서연 s3, 보호자 g1 = 지우)으로 확인한다.
"""

from datetime import timedelta

from tests.test_org_routes import _demo, _trial, client, clock  # noqa: F401 — 픽스처 재사용

MIN = 60_000


async def _room_a(t1) -> dict:
    cls = await t1.ok("GET", "/teacher/classes")
    return next(c for c in cls["classrooms"] if c["name"] == "5학년 A반")


async def test_class_flow_teacher_student_guardian(client, clock):  # noqa: F811
    t = await _trial(client)
    t1, s1, s2, g1 = [await _demo(client, t, k) for k in ("t1", "s1", "s2", "g1")]
    room = await _room_a(t1)
    cid = room["id"]
    # 시작 전: 학생 참여는 409
    assert (await s1.call("POST", f"/class-live/{cid}/join")).status_code == 409
    live = await t1.ok("POST", f"/class-live/{cid}/start", json={"minutes": 50})
    sess = live["sessions"][cid]
    assert sess["phase"] == "class" and sess["endAt"] - sess["startAt"] == 50 * MIN
    assert {m["id"] for m in sess["members"]} >= {s1.id, s2.id}
    # 학생 참여 → 학생에게는 자기만 보임
    mine = await s1.ok("POST", f"/class-live/{cid}/join")
    assert [m["id"] for m in mine["sessions"][cid]["members"]] == [s1.id]
    assert [j["id"] for j in mine["sessions"][cid]["joined"]] == [s1.id]
    await s2.ok("POST", f"/class-live/{cid}/join")
    other = await s2.ok("GET", "/class-live")
    assert [j["id"] for j in other["sessions"][cid]["joined"]] == [s2.id]
    # 보호자: 자기 아이만
    gv = await g1.ok("GET", "/class-live")
    assert [m["id"] for m in gv["sessions"][cid]["members"]] == [s1.id]
    # 학습지도자: ±5분, 줄여도 1분은 남김, 참여 빼기, 쉬는 시간, 다시 시작, 끝내기
    before = sess["endAt"]
    live = await t1.ok("POST", f"/class-live/{cid}/adjust", json={"deltaMin": 5})
    assert live["sessions"][cid]["endAt"] == before + 5 * MIN
    live = await t1.ok("POST", f"/class-live/{cid}/adjust", json={"deltaMin": -60})
    assert live["sessions"][cid]["endAt"] >= int(clock.now.timestamp() * 1000) + MIN
    live = await t1.ok("POST", f"/class-live/{cid}/remove", json={"studentId": s2.id})
    assert [j["id"] for j in live["sessions"][cid]["joined"]] == [s1.id]
    assert live["sessions"][cid]["removed"] == [s2.id]
    clock.now += timedelta(minutes=10)
    live = await t1.ok("POST", f"/class-live/{cid}/break", json={"minutes": 10})
    assert live["sessions"][cid]["phase"] == "break"
    live = await t1.ok("POST", f"/class-live/{cid}/resume", json={"minutes": 40})
    assert live["sessions"][cid]["phase"] == "class"
    live = await t1.ok("POST", f"/class-live/{cid}/end")
    assert live["sessions"][cid]["closedAt"] == int(clock.now.timestamp() * 1000)
    assert (await s1.call("POST", f"/class-live/{cid}/join")).status_code == 409
    # 남이 못 함: 학생이 시작, 다른 강의실 학생이 참여
    assert (
        await s1.call("POST", f"/class-live/{cid}/start", json={"minutes": 50})
    ).status_code == 403
    r = await t1.call("POST", f"/class-live/{cid}/start", json={"minutes": 0})
    assert r.status_code == 422


async def test_other_world_cannot_touch(client):  # noqa: F811
    a, b = await _trial(client), await _trial(client)
    t1a = await _demo(client, a, "t1")
    t1b, s1b = await _demo(client, b, "t1"), await _demo(client, b, "s1")
    cid = (await _room_a(t1a))["id"]
    assert (
        await t1b.call("POST", f"/class-live/{cid}/start", json={"minutes": 50})
    ).status_code == 404
    await t1a.ok("POST", f"/class-live/{cid}/start", json={"minutes": 50})
    assert (await s1b.call("POST", f"/class-live/{cid}/join")).status_code == 404
    assert cid not in (await s1b.ok("GET", "/class-live"))["sessions"]


async def test_owner_defaults_place_and_classrooms(client):  # noqa: F811
    t = await _trial(client)
    own1, t1, s1 = [await _demo(client, t, k) for k in ("own1", "t1", "s1")]
    cid = (await _room_a(t1))["id"]
    d = {"classMin": 40, "breakMin": 5, "games": False, "notifyGuardian": True, "showPlace": True}
    live = await own1.ok("PUT", "/class-live/defaults", json=d)
    assert live["defaults"] == {**d, "alertsMin": [10, 5]}
    await own1.ok("PUT", "/academy/timer-alerts", json={"alertsMin": [3, 15]})
    assert (await t1.ok("GET", "/class-live"))["defaults"]["alertsMin"] == [15, 3]
    bad = {**d, "classMin": 45}
    assert (await own1.call("PUT", "/class-live/defaults", json=bad)).status_code == 422
    assert (await t1.call("PUT", "/class-live/defaults", json=d)).status_code == 403
    live = await own1.ok("PUT", f"/class-live/{cid}/place", json={"place": " 3층 2강의실 "})
    assert live["places"][cid] == "3층 2강의실"
    stud = await s1.ok("GET", "/class-live")
    assert stud["defaults"]["classMin"] == 40 and stud["places"][cid] == "3층 2강의실"
    # 원장 강의실 만들기·담당 바꾸기
    dash = await own1.ok(
        "POST", "/owner/classrooms", json={"name": "6학년 B반", "plan": "", "teacherId": t1.id}
    )
    new = next(c for c in dash["classrooms"] if c["name"] == "6학년 B반")
    assert new["teacherId"] == t1.id
    assert "「6학년 B반」 강의실을 맡게 됐어요" in await t1.notices()
    dash = await own1.ok(
        "PUT", f"/owner/classrooms/{new['id']}/teacher", json={"teacherId": own1.id}
    )
    assert next(c for c in dash["classrooms"] if c["id"] == new["id"])["teacherId"] == own1.id
    r = await own1.call("POST", "/owner/classrooms", json={"name": "X", "teacherId": s1.id})
    assert r.status_code == 422
    assert (
        await t1.call("POST", "/owner/classrooms", json={"name": "X", "teacherId": t1.id})
    ).status_code == 403


async def test_posts_and_homework_done(client, clock):  # noqa: F811
    t = await _trial(client)
    t1, s1, s2, g1 = [await _demo(client, t, k) for k in ("t1", "s1", "s2", "g1")]
    cid = (await _room_a(t1))["id"]
    body = {"kind": "homework", "title": "교재 12쪽", "body": "분수 나눗셈", "due": "2026-11-12"}
    live = await t1.ok("POST", f"/class-live/{cid}/posts", json=body)
    post = live["posts"][0]
    assert post["kind"] == "homework" and post["due"] == "2026-11-12" and post["done"] == []
    r = await t1.call("POST", f"/class-live/{cid}/posts", json={**body, "due": None})
    assert r.status_code == 422
    assert (await s1.call("POST", f"/class-live/{cid}/posts", json=body)).status_code == 403
    clock.now += timedelta(minutes=1)  # 새 글이 위로
    live = await t1.ok(
        "POST", f"/class-live/{cid}/posts", json={"kind": "notice", "title": " 금요일 휴강 "}
    )
    assert live["posts"][0]["title"] == "금요일 휴강" and live["posts"][0]["due"] is None
    # 다 했어: 학생 본인만 보이고, 다시 누르면 취소
    mine = await s1.ok("POST", f"/class-live/posts/{post['id']}/done")
    assert next(p for p in mine["posts"] if p["id"] == post["id"])["done"] == [s1.id]
    await s2.ok("POST", f"/class-live/posts/{post['id']}/done")
    s2v = await s2.ok("GET", "/class-live")
    assert next(p for p in s2v["posts"] if p["id"] == post["id"])["done"] == [s2.id]
    tv = await t1.ok("GET", "/class-live")
    assert set(next(p for p in tv["posts"] if p["id"] == post["id"])["done"]) == {s1.id, s2.id}
    gv = await g1.ok("GET", "/class-live")
    assert next(p for p in gv["posts"] if p["id"] == post["id"])["done"] == [s1.id]
    mine = await s1.ok("POST", f"/class-live/posts/{post['id']}/done")
    assert next(p for p in mine["posts"] if p["id"] == post["id"])["done"] == []
    # 지우기: 담당만
    assert (await s1.call("DELETE", f"/class-live/posts/{post['id']}")).status_code == 403
    live = await t1.ok("DELETE", f"/class-live/posts/{post['id']}")
    assert all(p["id"] != post["id"] for p in live["posts"])


async def test_teacher_sees_only_own_rooms(client):  # noqa: F811
    """원장이 아닌 학습지도자는 학원의 다른 강의실(다른 담당) 수업·글을 못 본다."""
    t = await _trial(client)
    own1, t1 = await _demo(client, t, "own1"), await _demo(client, t, "t1")
    dash = await own1.ok("POST", "/owner/classrooms", json={"name": "원장반", "teacherId": own1.id})
    other = next(c for c in dash["classrooms"] if c["name"] == "원장반")["id"]
    await own1.ok("POST", f"/class-live/{other}/start", json={"minutes": 50})
    await own1.ok(
        "POST", f"/class-live/{other}/posts", json={"kind": "notice", "title": "원장반 공지"}
    )
    mine = await t1.ok("GET", "/class-live")
    assert other not in mine["sessions"] and all(p["classId"] != other for p in mine["posts"])
    assert other in (await own1.ok("GET", "/class-live"))["sessions"]
    r = await t1.call("POST", f"/class-live/{other}/end")
    assert r.status_code == 404


async def test_class_inputs_are_strict(client, clock):  # noqa: F811
    # 11-14 이상 입력 점검: minutes=true가 1분 수업이 됐고, 없는 날짜가 마감일로 저장됐고,
    # 참여 빼기 studentId에 길이·소속 확인이 없었다
    t = await _trial(client)
    t1 = await _demo(client, t, "t1")
    cid = (await _room_a(t1))["id"]
    r = await t1.call("POST", f"/class-live/{cid}/start", json={"minutes": True})
    assert r.status_code == 422
    body = {"kind": "homework", "title": "익힘책", "due": "2026-13-45"}
    assert (await t1.call("POST", f"/class-live/{cid}/posts", json=body)).status_code == 422
    await t1.ok("POST", f"/class-live/{cid}/start", json={"minutes": 50})
    r = await t1.call("POST", f"/class-live/{cid}/remove", json={"studentId": "x" * 5000})
    assert r.status_code == 422
    r = await t1.call("POST", f"/class-live/{cid}/remove", json={"studentId": "not-in-room"})
    assert r.status_code == 404


async def test_guardian_sees_red_alerts_of_every_linked_child(client, clock, db_session):  # noqa: F811
    # 11-14 점검 B5: 보호자 화면은 「연결된 첫 아이」(설계 §9-13)라 둘째 아이 🔴 알림이 안 보였다
    from app.models import Alert
    from app.models_org import Link

    t = await _trial(client)
    g1, s1 = [await _demo(client, t, k) for k in ("g1", "s1")]
    sid = (await s1.ok("POST", "/sessions", json={}))["id"]
    db_session.add(
        Link(
            student_account_id=f"{t}-s2",
            guardian_account_id=g1.id,
            status="연결됨",
            consent_at=clock.now.date(),  # 첫 아이(s1, 20일 전)보다 늦게 연결된 둘째
        )
    )
    db_session.add(
        Alert(
            session_id=sid,
            student_id=f"{t}-s2",
            trigger="K01",
            excerpt="합성 발췌",
            created_at=clock.now,
            expires_at=clock.now + timedelta(hours=72),
        )
    )
    await db_session.commit()
    alerts = await g1.ok("GET", "/guardian/alerts")
    assert [a["excerpt"] for a in alerts] == ["합성 발췌"]
    assert alerts[0]["childName"]  # 어느 아이인지 보인다


async def test_guardian_notice_shows_when_second_child_had_red_today(client, clock, db_session):  # noqa: F811
    from app.models import Session
    from app.models_org import Link

    t = await _trial(client)
    g1, s1 = [await _demo(client, t, k) for k in ("g1", "s1")]
    sid = (await s1.ok("POST", "/sessions", json={}))["id"]
    db_session.add(
        Link(
            student_account_id=f"{t}-s2",
            guardian_account_id=g1.id,
            status="연결됨",
            consent_at=clock.now.date(),
        )
    )
    row = await db_session.get(Session, sid)
    assert row is not None
    row.student_id, row.state = f"{t}-s2", "crisis"  # 둘째 아이가 오늘 🔴로 끝남(합성)
    await db_session.commit()
    card = await g1.ok("GET", "/guardian/today")
    assert card["alertNotice"]


async def test_trial_child_has_two_past_records_matching_streak(client):  # noqa: F811
    # 11-14 점검 U1: 체험 지우는 「연속 3일」인데 기록 화면이 「아직 기록이 없어요」였다
    t = await _trial(client)
    s1 = await _demo(client, t, "s1")
    records = await s1.ok("GET", "/student/records")
    assert len(records) == 2
    assert all(r["unit"] and r["total"] >= 1 for r in records)


async def test_trial_notice_names_the_real_unit(client):  # noqa: F811
    # 11-14 점검 U2: 체험 보호자 알림이 「분수의 덧셈·뺄셈」이었다(실제 범위는 분수 나눗셈)
    t = await _trial(client)
    g1 = await _demo(client, t, "g1")
    notices = await g1.ok("GET", "/notices")
    text = " ".join(str(n) for n in notices)
    assert "덧셈·뺄셈" not in text and "나눗셈" in text


async def test_student_notices_follow_polite_and_adults_get_polite(client, db_session):  # noqa: F811
    # 11-14 UT2(명세 4.12): 서버 알림이 「…들어왔어!」「…연결됐어!」 반말 고정이었다
    from app.models import Student
    from app.org_routes import kid_or_adult_text

    t = await _trial(client)
    s1 = await _demo(client, t, "s1")
    g1 = await _demo(client, t, "g1")
    kid = await db_session.get(Student, s1.id)
    assert kid is not None
    kid.polite = True
    await db_session.commit()
    assert await kid_or_adult_text(db_session, s1.id, "들어왔어!", "들어왔어요!") == "들어왔어요!"
    kid.polite = False
    await db_session.commit()
    assert await kid_or_adult_text(db_session, s1.id, "들어왔어!", "들어왔어요!") == "들어왔어!"
    assert await kid_or_adult_text(db_session, g1.id, "연결됐어!", "연결됐어요!") == "연결됐어요!"
