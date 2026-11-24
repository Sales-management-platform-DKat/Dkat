from datetime import date
from typing import Literal
from fastapi import APIRouter, Depends, Query, Response
from app.core.permissions import Actor, require_auth, require_owner_or_manager
from app.db.session import engine
from app.modules.reports import service
from app.modules.reports.export import export_filename, revenue_csv
from app.modules.reports.schemas import RevenueReportOut
from sqlalchemy import text

router=APIRouter(prefix='/reports',tags=['reports'])
ReportActor=Depends(require_owner_or_manager)
@router.get('/revenue')
def revenue(granularity:Literal['day','week','month','year']='day',date_from:date|None=Query(None,alias='from'),date_to:date|None=Query(None,alias='to'),branch_id:int|None=Query(None,alias='branchId',gt=0),actor:Actor=ReportActor):
 return service.revenue_report(actor,granularity,date_from,date_to,branch_id)
@router.get('/summary')
def summary(date_from:date|None=Query(None,alias='from'),date_to:date|None=Query(None,alias='to'),branch_id:int|None=Query(None,alias='branchId',gt=0),actor:Actor=ReportActor):
 return service.summary(actor,date_from,date_to,branch_id)
@router.get('/top-products')
def top_products(limit:int=Query(10,ge=1,le=50),sort_by:Literal['revenue','quantity']=Query('revenue',alias='sortBy'),date_from:date|None=Query(None,alias='from'),date_to:date|None=Query(None,alias='to'),branch_id:int|None=Query(None,alias='branchId',gt=0),actor:Actor=ReportActor):
 return service.top_products(actor,date_from,date_to,branch_id,limit,sort_by)
@router.get('/revenue/export')
def revenue_export(granularity:Literal['day','week','month','year']='day',date_from:date|None=Query(None,alias='from'),date_to:date|None=Query(None,alias='to'),branch_id:int|None=Query(None,alias='branchId',gt=0),delimiter:Literal['comma','semicolon']='comma',actor:Actor=ReportActor):
 report=service.revenue_report(actor,granularity,date_from,date_to,branch_id); label,code=('Toàn chuỗi',None)
 if branch_id is not None:
  with engine.connect() as db: row=db.execute(text('SELECT name,branch_code FROM branches WHERE branch_id=:id AND store_id=:store'),{'id':branch_id,'store':actor.store_id}).first()
  if row: label,code=row[0],row[1]
 filename=export_filename(granularity,report.date_from,report.date_to,code)
 return Response(content=revenue_csv(report,label,delimiter),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="{filename}"','Cache-Control':'no-store'})
