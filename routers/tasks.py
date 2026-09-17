import json
from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import get_db
from models import Poi, Task
from schemas import PoiPage, PoiRead, TaskCreate, TaskRead
from services.collect import collect_task
from services.config import settings


router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _task_read(task: Task) -> TaskRead:
    return TaskRead(
        id=task.id,
        city=task.city,
        keywords=json.loads(task.keywords_json),
        providers=json.loads(task.providers_json),
        status=task.status,
        total=task.total,
        error_message=task.error_message,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.post("", response_model=TaskRead, status_code=202)
def create_task(payload: TaskCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    unavailable = [name for name in payload.providers if not settings.key_for(name)]
    if unavailable:
        raise HTTPException(
            status_code=400,
            detail=f"以下平台未配置 API Key：{', '.join(unavailable)}",
        )

    task = Task(
        city=payload.city,
        keywords_json=json.dumps(payload.keywords, ensure_ascii=False),
        providers_json=json.dumps(payload.providers, ensure_ascii=False),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    background_tasks.add_task(collect_task, task.id, payload.pages)
    return _task_read(task)


@router.get("", response_model=list[TaskRead])
def list_tasks(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    tasks = db.scalars(select(Task).order_by(Task.id.desc()).limit(limit)).all()
    return [_task_read(task) for task in tasks]


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _task_read(task)


@router.get("/{task_id}/results", response_model=PoiPage)
def get_results(
    task_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    if db.get(Task, task_id) is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    condition = Poi.task_id == task_id
    total = db.scalar(select(func.count(Poi.id)).where(condition)) or 0
    rows = db.scalars(
        select(Poi)
        .where(condition)
        .order_by(Poi.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return PoiPage(
        items=[PoiRead.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{task_id}/export")
def export_results(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    rows = db.scalars(select(Poi).where(Poi.task_id == task_id).order_by(Poi.id)).all()

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "POI结果"
    headers = [
        "序号", "来源", "关键词", "名称", "分类", "地址", "省", "市", "区县",
        "电话", "经度", "纬度", "采集时间",
    ]
    sheet.append(headers)
    for index, poi in enumerate(rows, start=1):
        sheet.append([
            index, poi.provider, poi.keyword, poi.name, poi.category, poi.address,
            poi.province, poi.city, poi.district, poi.phone, poi.longitude,
            poi.latitude, poi.created_at,
        ])

    header_fill = PatternFill("solid", fgColor="17324D")
    for cell in sheet[1]:
        cell.fill = header_fill
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(horizontal="center")
    widths = [8, 12, 18, 30, 26, 46, 12, 12, 14, 20, 14, 14, 20]
    for column, width in zip(sheet.columns, widths):
        sheet.column_dimensions[column[0].column_letter].width = width
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    filename = quote(f"POI任务_{task_id}_{task.city}.xlsx")
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )
