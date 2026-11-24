from datetime import date, datetime, time, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import text
from app.core.permissions import Actor, get_accessible_branch_ids, require_branch_access
from app.db.session import engine
from app.modules.reports.schemas import RevenuePoint, RevenueReportOut, RevenueTotals, RevenueSummaryOut, SummaryMetric, CountMetric, PeriodRef, TopProductOut, TopProductsOut
VN = timezone(timedelta(hours=7))

def _window(d: date):
    return datetime.combine(d, time.min, tzinfo=VN).astimezone(timezone.utc).replace(tzinfo=None)
def _period_start(d, g):
    if g=='day': return d
    if g=='week': return d-timedelta(days=d.weekday())
    if g=='month': return d.replace(day=1)
    return d.replace(month=1,day=1)
def _next(d,g):
    if g=='day': return d+timedelta(days=1)
    if g=='week': return d+timedelta(days=7)
    if g=='month': return date(d.year+(d.month==12),d.month%12+1,1)
    return date(d.year+1,1,1)
def _label(d,g):
    return d.isoformat() if g=='day' else f'{d.isocalendar().year}-W{d.isocalendar().week:02d}' if g=='week' else f'{d.year}-{d.month:02d}' if g=='month' else str(d.year)
def _validate(actor, branch_id, date_from, date_to):
    if actor.role=='EMPLOYEE': raise HTTPException(403,'Employee role cannot view revenue reports.')
    if branch_id is not None:
        with engine.connect() as db: require_branch_access(db,actor,branch_id)
    elif actor.role!='OWNER': raise HTTPException(400,'Branch manager must select an assigned branch.')
    end=date_to or datetime.now(VN).date(); start=date_from or end-timedelta(days=29)
    if start>end: raise HTTPException(422,'Start date must be before or equal to end date.')
    return start,end
def _daily(actor, start, end, branch_id):
    lo,hi=_window(start),_window(end+timedelta(days=1)); branch_sql=' AND o.branch_id=:branch' if branch_id else ''
    params={'store':actor.store_id,'start':lo,'end':hi,'branch':branch_id}
    values={}
    with engine.connect() as db:
        for kind,sql in [('sales',f"SELECT o.paid_at AS at,o.total_amount AS amount FROM sales_orders o JOIN branches b ON b.branch_id=o.branch_id AND b.store_id=:store WHERE o.status='PAID' AND o.paid_at>=:start AND o.paid_at<:end{branch_sql}"),('preorders',f"SELECT o.fulfilled_at AS at,o.total_amount AS amount FROM preorders o JOIN branches b ON b.branch_id=o.branch_id AND b.store_id=:store WHERE o.status='FULFILLED' AND o.payment_status<>'REFUNDED' AND o.fulfilled_at>=:start AND o.fulfilled_at<:end{branch_sql}")]:
            for row in db.execute(text(sql),params).mappings():
                at=row['at']; at=at.replace(tzinfo=timezone.utc) if at.tzinfo is None else at
                day=at.astimezone(VN).date(); bucket=values.setdefault(day,{'sales':0.0,'sales_count':0,'preorders':0.0,'preorder_count':0})
                bucket[kind]+=float(row['amount']); bucket['sales_count' if kind=='sales' else 'preorder_count']+=1
    return values
def revenue_report(actor: Actor, granularity: str, date_from: date|None, date_to: date|None, branch_id: int|None):
    start,end=_validate(actor,branch_id,date_from,date_to); starts=[]; current=_period_start(start,granularity)
    while current<=end:
        starts.append(current); current=_next(current,granularity)
        if len(starts)>400: raise HTTPException(422,'Date range is too large; use a coarser granularity.')
    days=_daily(actor,start,end,branch_id); points=[]
    for period in starts:
        bucket={'sales':0.0,'sales_count':0,'preorders':0.0,'preorder_count':0}
        for d,v in days.items():
            if _period_start(d,granularity)==period:
                for k in bucket: bucket[k]+=v[k]
        sale,pre=bucket['sales'],bucket['preorders']; sc,pc=bucket['sales_count'],bucket['preorder_count']
        points.append(RevenuePoint(period=_label(period,granularity),period_start=period,period_end=_next(period,granularity)-timedelta(days=1),revenue=round(sale+pre,2),sales_revenue=round(sale,2),preorder_revenue=round(pre,2),order_count=sc+pc,sales_count=sc,preorder_count=pc))
    sale=sum(p.sales_revenue for p in points); pre=sum(p.preorder_revenue for p in points)
    return RevenueReportOut(granularity=granularity,date_from=start,date_to=end,branch_id=branch_id,timezone='UTC+07:00 (Asia/Ho_Chi_Minh)',totals=RevenueTotals(revenue=round(sale+pre,2),sales_revenue=round(sale,2),preorder_revenue=round(pre,2),order_count=sum(p.order_count for p in points)),points=points)
def _metric(cur,prev): return SummaryMetric(value=round(cur,2),previous=round(prev,2),change_percent=None if not prev else round((cur-prev)/prev*100,1))
def summary(actor,date_from,date_to,branch_id):
    start,end=_validate(actor,branch_id,date_from,date_to); length=(end-start).days+1; prev_end=start-timedelta(days=1); prev_start=prev_end-timedelta(days=length-1)
    def totals(a,b):
        days=_daily(actor,a,b,branch_id); sales=sum(v['sales'] for v in days.values()); pre=sum(v['preorders'] for v in days.values()); n=sum(v['sales_count']+v['preorder_count'] for v in days.values()); return sales,pre,n
    s,p,n=totals(start,end); ps,pp,pn=totals(prev_start,prev_end); rev=s+p; prev=ps+pp
    return RevenueSummaryOut(date_from=start,date_to=end,branch_id=branch_id,previous_period=PeriodRef(date_from=prev_start,date_to=prev_end),revenue=_metric(rev,prev),order_count=CountMetric(value=n,previous=pn,change_percent=_metric(n,pn).change_percent),average_order_value=_metric(rev/n if n else 0,prev/pn if pn else 0),sales_revenue=round(s,2),preorder_revenue=round(p,2))
def top_products(actor,date_from,date_to,branch_id,limit,sort_by):
    start,end=_validate(actor,branch_id,date_from,date_to); lo,hi=_window(start),_window(end+timedelta(days=1)); branch_sql=' AND o.branch_id=:branch' if branch_id else ''; params={'store':actor.store_id,'start':lo,'end':hi,'branch':branch_id}
    sql=f'''SELECT i.sku_snapshot sku,i.product_name_snapshot name,SUM(i.quantity) quantity,SUM(i.line_total) revenue,MAX(o.paid_at) last_at FROM sales_orders o JOIN branches b ON b.branch_id=o.branch_id AND b.store_id=:store JOIN sales_order_items i ON i.sales_order_id=o.sales_order_id WHERE o.status='PAID' AND o.paid_at>=:start AND o.paid_at<:end{branch_sql} GROUP BY i.sku_snapshot,i.product_name_snapshot UNION ALL SELECT i.sku_snapshot,i.product_name_snapshot,SUM(i.quantity),SUM(i.line_total),MAX(o.fulfilled_at) FROM preorders o JOIN branches b ON b.branch_id=o.branch_id AND b.store_id=:store JOIN preorder_items i ON i.preorder_id=o.preorder_id WHERE o.status='FULFILLED' AND o.payment_status<>'REFUNDED' AND o.fulfilled_at>=:start AND o.fulfilled_at<:end{branch_sql} GROUP BY i.sku_snapshot,i.product_name_snapshot'''
    with engine.connect() as db: rows=db.execute(text(sql),params).mappings().all()
    items={}
    for row in rows:
        x=items.setdefault(row['sku'],{'sku':row['sku'],'name':row['name'],'quantity':0,'revenue':0,'last':row['last_at']}); x['quantity']+=int(row['quantity']);x['revenue']+=float(row['revenue'])
        if row['last_at'] and (not x['last'] or row['last_at']>x['last']): x.update(name=row['name'],last=row['last_at'])
    items=sorted(items.values(),key=lambda x:(-x[sort_by],-(x['quantity'] if sort_by=='revenue' else x['revenue']),x['sku']))[:limit]
    return TopProductsOut(date_from=start,date_to=end,branch_id=branch_id,sort_by=sort_by,limit=limit,items=[TopProductOut(rank=i,sku=x['sku'],product_name=x['name'],quantity=x['quantity'],revenue=round(x['revenue'],2)) for i,x in enumerate(items,1)])
