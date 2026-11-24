import React, { useCallback, useEffect, useState } from 'react';
import { apiRequest } from './auth-client';

function flattenTree(nodes, depth = 0) {
  return nodes.flatMap(node => [{ ...node, depth }, ...flattenTree(node.children || [], depth + 1)]);
}

export default function CategoriesPage({ token, isOwner, notify }) {
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editor, setEditor] = useState(null);
  const [saving, setSaving] = useState(false);
  const [fieldErrors, setFieldErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const flat = flattenTree(categories);

  const load = useCallback(async () => {
    if (!token) { setLoading(false); return; }
    setLoading(true); setError(null);
    try { setCategories(await apiRequest('/categories', { token })); }
    catch (e) { setError(e); }
    finally { setLoading(false); }
  }, [token]);
  useEffect(() => { load(); }, [load]);

  const save = async (event) => {
    event.preventDefault(); setSaving(true); setFormError(null); setFieldErrors({});
    const data = new FormData(event.currentTarget);
    const body = { name: String(data.get('name') || '').trim(), parentCategoryId: data.get('parentCategoryId') ? Number(data.get('parentCategoryId')) : null, description: String(data.get('description') || '').trim() || null };
    try {
      if (editor.category) await apiRequest(`/categories/${editor.category.categoryId}`, { method: 'PUT', token, body: JSON.stringify(body) });
      else await apiRequest('/categories', { method: 'POST', token, body: JSON.stringify(body) });
      setEditor(null); await load(); notify('Category saved to the database.');
    } catch (e) {
      if (e.code === 'VALIDATION_ERROR' && Array.isArray(e.details)) {
        const mapped = {};
        e.details.forEach(item => { const key = String(item.field || '').split('.').at(-1); if (['name', 'parentCategoryId'].includes(key)) mapped[key] = item.message; });
        if (Object.keys(mapped).length) setFieldErrors(mapped); else setFormError(e);
      } else { setFormError(e); if (e.status === 409 || e.code === 'CONFLICT') notify('\u0044anh m\u1ee5c b\u1ecb tr\u00f9ng ho\u1eb7c c\u00f2n d\u1eef li\u1ec7u li\u00ean quan n\u00ean kh\u00f4ng th\u1ec3 thay \u0111\u1ed5i.', 'error'); }
    } finally { setSaving(false); }
  };

  const toggleStatus = async (category) => {
    const status = category.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE';
    try { await apiRequest(`/categories/${category.categoryId}/status`, { method: 'PATCH', token, body: JSON.stringify({ status }) }); await load(); }
    catch (e) { if (e.status === 409 || e.code === 'CONFLICT') notify('\u0044anh m\u1ee5c b\u1ecb tr\u00f9ng ho\u1eb7c c\u00f2n d\u1eef li\u1ec7u li\u00ean quan n\u00ean kh\u00f4ng th\u1ec3 thay \u0111\u1ed5i.', 'error'); else setError(e); }
  };

  if (!token) return <section className="panel"><h3>Sign in to your store account</h3><p className="muted">Live categories are available after signing in.</p><a className="btn primary" href="#/login">Sign in</a></section>;

  return <>
    <div className="toolbar">{isOwner && <button className="btn primary" onClick={() => { setFieldErrors({}); setFormError(null); setEditor({ category: null }); }}>+ Add category</button>}</div>
    {error && <div className="notice amber" role="alert">{error.message}</div>}
    <section className="panel"><div className="table-wrap"><table><thead><tr><th>Category</th><th>Description</th><th>Status</th><th>Actions</th></tr></thead><tbody>
      {loading ? <tr><td colSpan="4"><div className="product-skeleton" aria-label="Loading categories" aria-busy="true">{[0,1,2].map(x=><div className="skeleton-row" key={x}><i/><i/><i/><i/></div>)}</div></td></tr> : flat.length ? flat.map(category => <tr key={category.categoryId}><td><span style={{ paddingInlineStart: `${category.depth * 22}px` }}>{category.depth ? '↳ ' : ''}{category.name}</span></td><td>{category.description || '—'}</td><td><span className={'badge '+(category.status==='ACTIVE'?'green':'amber')}>{category.status==='ACTIVE'?'Active':'Inactive'}</span></td><td>{isOwner ? <div className="actions"><button className="link" onClick={()=>{setFieldErrors({});setFormError(null);setEditor({category});}}>Edit</button><button className="link danger" onClick={()=>toggleStatus(category)}>{category.status==='ACTIVE'?'Deactivate':'Activate'}</button></div> : 'View only'}</td></tr>) : <tr><td colSpan="4"><div className="empty"><h3>No categories found</h3></div></td></tr>}
    </tbody></table></div></section>
    {editor && <div className="overlay" onClick={()=>setEditor(null)}><section className="dialog" role="dialog" aria-modal="true" onClick={e=>e.stopPropagation()}><button className="close" onClick={()=>setEditor(null)}>×</button><span className="eyebrow">CATEGORY</span><h2>{editor.category?'Edit category':'Add category'}</h2>{formError && <div className="notice amber" role="alert">{formError.message}</div>}<form onSubmit={save}>
      <label className="field">Name<input name="name" defaultValue={editor.category?.name||''} required maxLength="100" aria-invalid={!!fieldErrors.name}/>{fieldErrors.name&&<small className="field-error">{fieldErrors.name}</small>}</label>
      <label className="field">Parent category<select name="parentCategoryId" defaultValue={editor.category?.parentCategoryId||''}><option value="">No parent</option>{flat.filter(c=>c.categoryId!==editor.category?.categoryId).map(c=><option value={c.categoryId} key={c.categoryId}>{'— '.repeat(c.depth)}{c.name}</option>)}</select>{fieldErrors.parentCategoryId&&<small className="field-error">{fieldErrors.parentCategoryId}</small>}</label>
      <label className="field">Description<textarea name="description" defaultValue={editor.category?.description||''} maxLength="16000"/></label>
      <button className="btn primary" disabled={saving}>{saving?'Saving…':'Save category'}</button>
    </form></section></div>}
  </>;
}
