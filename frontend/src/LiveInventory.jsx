import React, { useEffect, useMemo, useState } from 'react';
import { apiRequest } from './auth-client';
import { useCurrentBranch } from './branches/BranchContext';
import CsvStockImport from './CsvStockImport';

const blankLine = () => ({ variantId: '', quantity: '' });

export default function LiveInventory({ token, notify }) {
  const { branchId, branches } = useCurrentBranch();
  const [items, setItems] = useState([]);
  const [movements, setMovements] = useState([]);
  const [movementType, setMovementType] = useState('');
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('ALL');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [reload, setReload] = useState(0);
  const [editor, setEditor] = useState(null);
  const [lines, setLines] = useState([blankLine()]);
  const [note, setNote] = useState('');
  const [reason, setReason] = useState('HU_HONG');
  const [saving, setSaving] = useState(false);
  const [fieldError, setFieldError] = useState('');

  useEffect(() => { let active = true; setLoading(true); setError(null); const params = new URLSearchParams({page:'1',size:'100'}); if (branchId && branchId !== 'all') params.set('branchId',String(branchId)); if(query.trim())params.set('keyword',query.trim()); if(filter==='LOW'||filter==='OUT')params.set('lowStock','true'); apiRequest(`/inventory?${params}`,{token}).then(data=>{if(active)setItems(data)}).catch(e=>{if(active)setError(e)}).finally(()=>{if(active)setLoading(false)}); return()=>{active=false}; }, [token,branchId,query,filter,reload]);
  useEffect(() => { let active=true; const params=new URLSearchParams({page:'1',size:'50'}); if(branchId&&branchId!=='all')params.set('branchId',String(branchId)); if(query.trim())params.set('keyword',query.trim()); if(movementType)params.set('type',movementType); apiRequest(`/inventory/movements?${params}`,{token}).then(data=>{if(active)setMovements(data)}).catch(()=>{if(active)setMovements([])}); return()=>{active=false}; },[token,branchId,query,movementType,reload]);

  const visible = useMemo(() => items.filter(item => filter === 'ALL' || (filter === 'OUT' ? item.available <= 0 : item.available > 0 && item.available < 5)), [items, filter]);
  const branchName = (id) => branches.find(b => String(b.id ?? b.branchId) === String(id))?.name || items.find(i => String(i.branchId) === String(id))?.branchName || `Branch ${id}`;
  const open = (type) => { setEditor(type); setLines([blankLine()]); setNote(''); setReason('HU_HONG'); setFieldError(''); };
  const setLine = (index, key, value) => setLines(current => current.map((line, i) => i === index ? { ...line, [key]: value } : line));
  const submit = async (event) => {
    event.preventDefault(); setFieldError('');
    if (!branchId || branchId === 'all') { setFieldError('Choose one branch before changing stock.'); return; }
    const prepared = lines.map(line => ({ variantId: Number(line.variantId), quantity: Number(line.quantity), countedQuantity: Number(line.quantity) }));
    if (!prepared.length || prepared.some(x => !x.variantId || !Number.isInteger(x.quantity) || (editor === 'COUNT' ? x.countedQuantity < 0 : x.quantity <= 0))) { setFieldError('Choose a SKU and enter a valid whole-number quantity for every row.'); return; }
    if (new Set(prepared.map(x => x.variantId)).size !== prepared.length) { setFieldError('Each SKU can appear only once.'); return; }
    if (editor === 'EXPORT' && prepared.some(line => line.quantity > (items.find(i => i.variantId === line.variantId && String(i.branchId) === String(branchId))?.available || 0))) { setFieldError('Export quantity exceeds available stock for at least one SKU.'); return; }
    setSaving(true);
    try {
      const body = { branchId: Number(branchId), note: note.trim() || null, items: prepared.map(line => editor === 'COUNT' ? { variantId: line.variantId, countedQuantity: line.countedQuantity } : { variantId: line.variantId, quantity: line.quantity }) };
      if (editor === 'EXPORT') body.reason = reason;
      await apiRequest(`/inventory/${editor === 'IMPORT' ? 'import' : editor === 'EXPORT' ? 'export' : 'stocktake'}`, { method: 'POST', token, body: JSON.stringify(body) });
      setEditor(null); setReload(x => x + 1); notify(editor === 'IMPORT' ? 'Stock received successfully.' : editor === 'EXPORT' ? 'Stock exported successfully.' : 'Stocktake recorded successfully.');
    } catch (e) {
      if (e.code === 'INSUFFICIENT_STOCK') setFieldError(`INSUFFICIENT_STOCK: ${e.message}`);
      else if (e.code === 'STOCK_BELOW_RESERVED') setFieldError(`STOCK_BELOW_RESERVED: counted stock cannot be lower than the reserved quantity (${e.details?.reserved ?? 'unknown'}).`);
      else setFieldError(e.message || 'Unable to update stock.');
    } finally { setSaving(false); }
  };

  const statusOf = (available) => available <= 0 ? ['Out of stock', 'red'] : available < 5 ? ['Low stock', 'amber'] : ['In stock', 'green'];
  return <>
    <div className="toolbar"><input placeholder="Search SKU, product, or variant" value={query} onChange={e=>setQuery(e.target.value)}/><select value={filter} onChange={e=>setFilter(e.target.value)}><option value="ALL">All stock</option><option value="LOW">Low stock (&lt; 5)</option><option value="OUT">Out of stock</option></select>{branchId !== 'all' && <><CsvStockImport token={token} notify={notify} onImported={()=>setReload(x=>x+1)}/><button className="btn primary" onClick={()=>open('IMPORT')}>Receive stock</button><button className="btn outline" onClick={()=>open('EXPORT')}>Export stock</button><button className="btn outline" onClick={()=>open('COUNT')}>Stocktake</button></>}</div>
    {error && <div className="notice amber" role="alert">{error.message}</div>}
    <section className="panel"><div className="table-wrap"><table><thead><tr>{[...(branchId==='all'?['Branch']:[]),'Product / variant','SKU','On hand','Reserved','Available','Status'].map(x=><th key={x}>{x}</th>)}</tr></thead><tbody>{loading?<tr><td colSpan={branchId==='all'?7:6}><div className="product-skeleton" aria-busy="true">{[0,1,2].map(i=><div className="skeleton-row" key={i}><i/><i/><i/></div>)}</div></td></tr>:visible.length?visible.map(item=>{const [label,tone]=statusOf(item.available);return <tr key={`${item.branchId}-${item.variantId}`}>{branchId==='all'&&<td>{branchName(item.branchId)}</td>}<td><b>{item.productName}</b><small className="block muted">{item.variantName}</small></td><td>{item.sku}</td><td>{item.quantity}</td><td>{item.reserved}</td><td>{item.available}</td><td><span className={`badge ${tone}`}>{label}</span></td></tr>;}):<tr><td colSpan={branchId==='all'?7:6}><div className="empty"><h3>No inventory found</h3></div></td></tr>}</tbody></table></div></section>
    <section className="panel"><div className="section-title"><h3>Movement history</h3><select aria-label="Filter movement type" value={movementType} onChange={e=>setMovementType(e.target.value)}><option value="">All movements</option>{['IMPORT','EXPORT','SALE','PREORDER_FULFILLMENT','ADJUSTMENT'].map(t=><option value={t} key={t}>{t}</option>)}</select></div><div className="table-wrap"><table><thead><tr>{[...(branchId==='all'?['Branch']:[]),'Time','SKU','Type','Quantity','Actor','Note','Reference'].map(x=><th key={x}>{x}</th>)}</tr></thead><tbody>{movements.length?movements.map(m=><tr key={m.movementId}>{branchId==='all'&&<td>{m.branchName}</td>}<td>{new Date(m.createdAt).toLocaleString()}</td><td>{m.sku}</td><td><span className={`badge ${m.quantityChange>0?'green':m.quantityChange<0?'red':'amber'}`}>{m.movementType}</span></td><td>{m.quantityChange>0?'+':''}{m.quantityChange}</td><td>{m.actorName||m.createdBy}</td><td>{m.note||m.reason||'—'}</td><td>{m.referenceId||'—'}</td></tr>):<tr><td colSpan={branchId==='all'?8:7}><div className="empty">No stock movements found.</div></td></tr>}</tbody></table></div></section>
    {editor && <div className="overlay" onClick={()=>!saving&&setEditor(null)}><form className="dialog product-dialog" role="dialog" aria-modal="true" onSubmit={submit} onClick={e=>e.stopPropagation()}><button type="button" className="close" onClick={()=>setEditor(null)}>×</button><span className="eyebrow">INVENTORY / {editor}</span><h2>{editor==='IMPORT'?'Receive stock':editor==='EXPORT'?'Export stock':'Stocktake'}</h2><label className="field">Branch<select value={branchId} disabled><option value={branchId}>{branchName(branchId)}</option></select></label>{lines.map((line,index)=><div className="attribute-row" key={index}><label className="field">SKU / variant<select required value={line.variantId} onChange={e=>setLine(index,'variantId',e.target.value)}><option value="">Choose SKU</option>{items.filter(item=>String(item.branchId)===String(branchId)).map(item=><option key={item.variantId} value={item.variantId}>{item.sku} · {item.variantName}{editor==='EXPORT'?` (available ${item.available})`:''}</option>)}</select></label><label className="field">{editor==='COUNT'?'Counted quantity':'Quantity'}<input aria-label="Quantity" type="number" min={editor==='COUNT'?'0':'1'} step="1" required value={line.quantity} onChange={e=>setLine(index,'quantity',e.target.value)}/></label><button type="button" className="link danger" onClick={()=>setLines(current=>current.filter((_,i)=>i!==index))} disabled={lines.length===1}>Remove</button></div>)}<button type="button" className="btn outline" onClick={()=>setLines(current=>[...current,blankLine()])}>+ Add SKU</button>{editor==='EXPORT'&&<label className="field">Reason<select value={reason} onChange={e=>setReason(e.target.value)}><option value="HU_HONG">Damaged</option><option value="MAU">Sample</option><option value="KHAC">Other</option></select></label>}<label className="field">Note<textarea value={note} maxLength={255} onChange={e=>setNote(e.target.value)}/></label>{fieldError&&<div className="notice amber" role="alert">{fieldError}</div>}<div className="actions"><button type="button" className="btn outline" onClick={()=>setEditor(null)}>Cancel</button><button className="btn primary" disabled={saving}>{saving?'Saving…':'Confirm'}</button></div></form></div>}
  </>;
}
