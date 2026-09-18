"""绿地台账接口测试。"""

from datetime import date


def space_payload(**overrides):
    payload = {
        "name": "运河文化公园",
        "district": "拱墅区",
        "address": "运河东路 128 号",
        "green_type": "park",
        "maintenance_grade": "level1",
        "area_sqm": 46200,
        "manager": "俞晓慧",
        "contact_phone": "0571-88221009",
        "plant_summary": "垂柳 120 株、麦冬地被 12000 平方米",
        "established_date": "2012-09-28",
    }
    payload.update(overrides)
    return payload


def test_create_generates_code_with_year_prefix(api):
    data = api.data(api.post("/api/v1/green-spaces", space_payload()), 201)
    assert data["code"] == f"GS-{date.today():%Y}-0001"
    assert data["green_type_label"] == "公园绿地"
    assert data["status"] == "normal"
    assert data["area_sqm"] == 46200.0


def test_create_keeps_custom_code_and_rejects_duplicate(api):
    first = api.data(api.post("/api/v1/green-spaces", space_payload(code="GS-XH-0007")), 201)
    assert first["code"] == "GS-XH-0007"

    response = api.post("/api/v1/green-spaces", space_payload(name="重复编号绿地", code="GS-XH-0007"))
    assert response.status_code == 409
    assert "已存在" in response.get_json()["message"]


def test_create_reports_field_errors_together(api):
    response = api.post("/api/v1/green-spaces", {
        "name": "",
        "district": "拱墅区",
        "green_type": "unknown-type",
        "maintenance_grade": "level9",
        "area_sqm": -5,
        "contact_phone": "abc",
        "established_date": "2012/13/40",
    })
    assert response.status_code == 422
    details = response.get_json()["data"]
    assert set(details) == {
        "name", "green_type", "maintenance_grade", "area_sqm", "contact_phone", "established_date"
    }
    assert "取值不合法" in details["green_type"]


def test_list_supports_keyword_and_enum_filters(api):
    api.post("/api/v1/green-spaces", space_payload())
    api.post("/api/v1/green-spaces", space_payload(name="西溪里小区绿地", district="西湖区",
                                                  address="文二西路 788 号",
                                                  green_type="residential", maintenance_grade="level3"))

    data = api.data(api.get("/api/v1/green-spaces", keyword="运河"))
    assert data["meta"]["total"] == 1
    assert data["items"][0]["name"] == "运河文化公园"
    assert data["summary"]["total_area"] == 46200.0

    data = api.data(api.get("/api/v1/green-spaces", green_type="residential", district="西湖区"))
    assert [item["name"] for item in data["items"]] == ["西溪里小区绿地"]

    # 非法枚举值被忽略，等价于不过滤
    data = api.data(api.get("/api/v1/green-spaces", green_type="not-a-type"))
    assert data["meta"]["total"] == 2


def test_list_supports_sorting_and_pagination(api):
    api.post("/api/v1/green-spaces", space_payload(name="小绿地", area_sqm=100))
    api.post("/api/v1/green-spaces", space_payload(name="大绿地", area_sqm=9000))

    data = api.data(api.get("/api/v1/green-spaces", sort="area_sqm", order="desc", page_size=1))
    assert data["items"][0]["name"] == "大绿地"
    assert data["meta"] == {"page": 1, "page_size": 1, "total": 2, "pages": 2}

    page2 = api.data(api.get("/api/v1/green-spaces", sort="area_sqm", order="desc",
                             page_size=1, page=2))
    assert page2["items"][0]["name"] == "小绿地"


def test_options_excludes_archived(api, make_space):
    make_space(name="在用绿地")
    make_space(name="归档绿地", status="archived")
    data = api.data(api.get("/api/v1/green-spaces/options"))
    assert [item["name"] for item in data["items"]] == ["在用绿地"]


def test_update_ignores_code_change(api, make_space):
    space = make_space(code="GS-FIX-0001")
    data = api.data(api.put(f"/api/v1/green-spaces/{space.id}", space_payload(code="GS-NEW-9999")))
    assert data["code"] == "GS-FIX-0001"
    assert data["name"] == "运河文化公园"


def test_detail_and_profile_aggregate_related_data(api, make_task, make_record):
    task = make_task()
    make_record(task=task, work_hours=8)
    make_record(task=task, work_hours=4, quality_result="pending", record_date=date(2026, 3, 20))

    data = api.data(api.get(f"/api/v1/green-spaces/{task.green_space_id}/profile"))
    assert data["green_space"]["name"] == task.green_space.name
    assert data["statistics"]["record_count"] == 2
    assert data["statistics"]["total_work_hours"] == 12.0
    assert data["statistics"]["last_maintenance_date"] == "2026-03-20"
    assert data["statistics"]["task_status"]["completed"] == 1
    assert len(data["recent_records"]) == 2


def test_delete_is_blocked_until_force(api, make_task):
    task = make_task()
    space_id = task.green_space_id

    response = api.delete(f"/api/v1/green-spaces/{space_id}")
    assert response.status_code == 409
    assert response.get_json()["data"]["maintenance_task"] == 1

    data = api.data(api.delete(f"/api/v1/green-spaces/{space_id}", force="true"))
    assert data == {"maintenance_task": 1, "maintenance_record": 0, "plant_replacement": 0}
    assert api.get(f"/api/v1/green-spaces/{space_id}").status_code == 404


def test_timeline_merges_events_and_marks_long_gaps(api, make_task, make_record, make_replacement):
    task = make_task()
    space_id = task.green_space_id
    # 待复检记录使任务保持「进行中」，计划日期已过 -> 任务逾期
    make_record(task=task, record_date=date(2026, 3, 12), quality_result="pending")
    replacement = make_replacement(space=task.green_space, replace_date=date(2026, 3, 15))
    make_record(space=task.green_space, record_date=date(2026, 1, 5))

    data = api.data(api.get(f"/api/v1/green-spaces/{space_id}/timeline"))
    assert data["long_gap_days"] == 30
    assert data["statistics"] == {
        "total": 4,
        "task_count": 1,
        "record_count": 2,
        "replacement_count": 1,
        "long_gap_count": 1,
        "longest_gap_days": 64,
    }

    items = data["items"]
    assert [(item["type"], item["event_date"]) for item in items] == [
        ("replacement", "2026-03-15"),
        ("record", "2026-03-12"),
        ("task", "2026-03-10"),
        ("record", "2026-01-05"),
    ]
    assert [item["gap_days"] for item in items] == [3, 2, 64, None]
    assert [item["is_long_gap"] for item in items] == [False, False, True, False]

    # 关键字段完整，且任务逾期标记沿用模型逻辑
    assert items[0]["type_label"] == "绿植更换"
    assert items[0]["no"] == replacement.replacement_no
    assert items[2]["is_overdue"] is True


def test_timeline_same_day_ordering_is_replacement_record_task(api, make_task, make_record,
                                                               make_replacement):
    task = make_task(plan_date=date(2026, 5, 1))
    make_record(task=task, record_date=date(2026, 5, 1))
    make_replacement(space=task.green_space, replace_date=date(2026, 5, 1))

    data = api.data(api.get(f"/api/v1/green-spaces/{task.green_space_id}/timeline"))
    assert [item["type"] for item in data["items"]] == ["replacement", "record", "task"]
    assert [item["gap_days"] for item in data["items"]] == [0, 0, None]


def test_timeline_filter_by_types_recalculates_gaps(api, client, make_task, make_record,
                                                     make_replacement):
    task = make_task(plan_date=date(2026, 3, 10))
    make_record(task=task, record_date=date(2026, 3, 12))
    make_replacement(space=task.green_space, replace_date=date(2026, 3, 15))
    make_record(space=task.green_space, record_date=date(2026, 1, 5))

    path = f"/api/v1/green-spaces/{task.green_space_id}/timeline"

    # 只看任务与养护记录：更换被过滤，间隔按筛选后的结果重算；
    # 各类型总数不受筛选影响，仍可用于类型按钮上的数量徽标
    data = api.data(api.get(path, types="task,record"))
    assert [item["type"] for item in data["items"]] == ["record", "task", "record"]
    assert [item["gap_days"] for item in data["items"]] == [2, 64, None]
    assert data["statistics"]["total"] == 3
    assert data["statistics"]["replacement_count"] == 1
    assert data["statistics"]["long_gap_count"] == 1

    # 支持 types 重复传参（多值取并集）
    response = client.get(path, query_string=[("types", "record"), ("types", "replacement")])
    data = api.data(response)
    assert {item["type"] for item in data["items"]} == {"record", "replacement"}

    # 非法类型被忽略，等价于返回全部
    data = api.data(api.get(path, types="unknown"))
    assert data["statistics"]["total"] == 4


def test_timeline_empty(api, make_space):
    space = make_space()
    data = api.data(api.get(f"/api/v1/green-spaces/{space.id}/timeline"))
    assert data["items"] == []
    assert data["statistics"]["total"] == 0
    assert data["statistics"]["longest_gap_days"] == 0
