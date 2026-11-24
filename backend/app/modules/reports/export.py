import csv,io
from datetime import date
from app.modules.reports.schemas import RevenueReportOut
DELIMITERS={'comma':',','semicolon':';'}
HEADERS=['Chi nhánh','Kỳ','Từ ngày','Đến ngày','Doanh thu (VND)','Doanh thu bán hàng (VND)','Doanh thu đặt trước (VND)','Số đơn','Số đơn bán','Số đơn đặt trước']
def revenue_csv(report:RevenueReportOut,branch_label:str,delimiter='comma')->bytes:
 out=io.StringIO(); writer=csv.writer(out,delimiter=DELIMITERS[delimiter],lineterminator='\r\n'); writer.writerow(HEADERS)
 label="'"+branch_label if branch_label[:1] in ('=','+','-','@') else branch_label
 for p in report.points: writer.writerow([label,p.period,p.period_start.isoformat(),p.period_end.isoformat(),round(p.revenue),round(p.sales_revenue),round(p.preorder_revenue),p.order_count,p.sales_count,p.preorder_count])
 t=report.totals;writer.writerow([label,'Tổng cộng',report.date_from.isoformat(),report.date_to.isoformat(),round(t.revenue),round(t.sales_revenue),round(t.preorder_revenue),t.order_count,sum(p.sales_count for p in report.points),sum(p.preorder_count for p in report.points)])
 return b'\xef\xbb\xbf'+out.getvalue().encode('utf-8')
def export_filename(granularity:str,date_from:date,date_to:date,branch_code:str|None)->str:
 scope=''.join(c for c in (branch_code or 'toan-chuoi') if c.isalnum() or c in '-_') or 'chi-nhanh';return f'doanh-thu_{granularity}_{date_from.isoformat()}_{date_to.isoformat()}_{scope}.csv'
