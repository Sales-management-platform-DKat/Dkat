import React, { useCallback, useEffect, useState } from 'react';
import { apiRequest } from './auth-client';

const PAGE_SIZE = 10;

function SkeletonRows() {
  return <div className="panel product-skeleton" aria-label="Loading products" aria-busy="true">
    {[0, 1, 2, 3].map((row) => <div className="skeleton-row" key={row}><i/><i/><i/><i/></div>)}
  </div>;
}

function ErrorMessage({ error }) {
  if (!error) return null;
  return <div className="notice amber" role="alert">{error.message}</div>;
}

export default function ProductsPage({ token, isOwner, notify }) {
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [query, setQuery] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [status, setStatus] = useState('ACTIVE');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editor, setEditor] = useState(null);
  const [formError, setFormError] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [imagePreview, setImagePreview] = useState('');
  const [detail, setDetail] = useState(null);
  const [attributes, setAttributes] = useState([]);
  const [variantRows, setVariantRows] = useState([{ name: 'Size', type: 'TEXT', value: 'M' }, { name: 'M\u00e0u', type: 'TEXT', value: '\u0110en' }]);

  const loadProducts = useCallback(async () => {
    if (!token) { setLoading(false); setError(null); return; }
    setLoading(true); setError(null);
    try {
      const params = new URLSearchParams({ page: String(page), size: String(PAGE_SIZE), status, sort: '-createdAt' });
      if (query.trim()) params.set('keyword', query.trim());
      if (categoryId) params.set('categoryId', categoryId);
      const [items, categoryItems] = await Promise.all([
        apiRequest(`/products?${params}`, { token }),
        apiRequest('/categories?status=ACTIVE', { token }),
      ]);
      setProducts(items); setCategories(categoryItems);
    } catch (e) { setError(e); }
    finally { setLoading(false); }
  }, [token, page, status, categoryId, query]);

  useEffect(() => { const timer = setTimeout(loadProducts, query ? 250 : 0); return () => clearTimeout(timer); }, [loadProducts, query]);

  const openEdit = async (product) => {
    setFieldErrors({}); setFormError(null); setImagePreview(product.imageUrl||''); setEditor({ mode: 'edit', product });
    try {
      const fresh = await apiRequest(`/products/${product.product_id}`, { token });
      setEditor(current => current?.product?.product_id === product.product_id ? { mode: 'edit', product: fresh } : current);
    } catch (e) { setFormError(e); }
  };

  const openVariant = async (product) => {
    setFormError(null); setFieldErrors({}); setDetail(null); setEditor({ mode: 'variant', product });
    try {
      const [fresh, attrs] = await Promise.all([
        apiRequest(`/products/${product.product_id}`, { token }), apiRequest('/attributes', { token }),
      ]);
      setDetail(fresh); setAttributes(attrs);
    } catch (e) { setFormError(e); }
  };

  const mapValidation = (e) => {
    if (e.code !== 'VALIDATION_ERROR' || !Array.isArray(e.details)) return false;
    const mapped = {};
    e.details.forEach(item => {
      const key = String(item.field || '').split('.').at(-1);
      const names = { categoryId: 'categoryId', name: 'name', productCode: 'productCode', price: 'price', variantName: 'variantName', sku: 'sku' };
      if (names[key]) mapped[names[key]] = item.message;
    });
    setFieldErrors(mapped); return Object.keys(mapped).length > 0;
  };

  const saveProduct = async (event) => {
    event.preventDefault(); setSaving(true); setFieldErrors({}); setFormError(null);
    const data = new FormData(event.currentTarget);
    const body = {
      name: String(data.get('name') || '').trim(),
      categoryId: Number(data.get('categoryId')),
      description: String(data.get('description') || '').trim() || null,
      imageUrl: String(data.get('imageUrl') || '').trim() || null,
      productCode: String(data.get('productCode') || '').trim() || null,
    };
    try {
      const requestedStatus = String(data.get('status') || 'ACTIVE');
      let product = editor.mode === 'edit'
        ? await apiRequest(`/products/${editor.product.product_id || editor.product.productId}`, { method: 'PUT', token, body: JSON.stringify({ ...body, productCode: undefined }) })
        : await apiRequest('/products', { method: 'POST', token, body: JSON.stringify(body) });
      if (requestedStatus !== (editor.product.status || 'ACTIVE')) product = await apiRequest(`/products/${product.product_id || product.productId}/status`, { method: 'PATCH', token, body: JSON.stringify({ status: requestedStatus }) });
      if (editor.mode === 'new') {
        setEditor({ mode: 'variant', product }); setVariantRows([{ name: 'Size', type: 'TEXT', value: 'M' }, { name: 'M\u00e0u', type: 'TEXT', value: '\u0110en' }]);
        const [fresh, attrs] = await Promise.all([apiRequest(`/products/${product.productId}`, { token }), apiRequest('/attributes', { token })]);
        setDetail(fresh); setAttributes(attrs);
      } else setEditor(null);
      await loadProducts();
      notify('Product saved to the database.');
    } catch (e) { if (!mapValidation(e)) setFormError(e); }
    finally { setSaving(false); }
  };

  const changeStatus = async (product) => {
    const nextStatus = status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE';
    try {
      await apiRequest(`/products/${product.product_id}/status`, { method: 'PATCH', token, body: JSON.stringify({ status: nextStatus }) });
      await loadProducts();
    } catch (e) { setError(e); }
  };

  const saveVariant = async (event) => {
    event.preventDefault(); setSaving(true); setFieldErrors({}); setFormError(null);
    const data = new FormData(event.currentTarget);
    try {
      const prepared = [];
      for (let i = 0; i < data.getAll('attributeName').length; i += 1) {
        const name = String(data.getAll('attributeName')[i] || '').trim();
        if (!name) continue;
        const type = data.getAll('attributeType')[i];
        let attr = attributes.find(a => a.name.toLocaleLowerCase() === name.toLocaleLowerCase());
        if (attr && attr.dataType !== type) throw Object.assign(new Error('Attribute has a different data type.'), { code: 'ATTRIBUTE_TYPE' });
        if (!attr) {
          attr = await apiRequest('/attributes', { method: 'POST', token, body: JSON.stringify({ name, dataType: type }) });
          setAttributes(current => [...current, attr]);
        }
        const raw = data.getAll('attributeValue')[i];
        prepared.push({ attributeId: attr.attributeId, value: type === 'NUMBER' ? Number(raw) : type === 'BOOLEAN' ? raw === 'true' : String(raw || '') });
      }
      const product = detail || editor.product;
      const body = { variantName: String(data.get('variantName') || '').trim(), price: Number(data.get('price')), sku: String(data.get('sku') || '').trim() || null, attributes: prepared };
      await apiRequest(`/products/${product.product_id || product.productId}/variants`, { method: 'POST', token, body: JSON.stringify(body) });
      const fresh = await apiRequest(`/products/${product.product_id || product.productId}`, { token });
      setDetail(fresh); setEditor({ mode: 'variant', product: fresh }); setVariantRows([{ name: 'Size', type: 'TEXT', value: 'M' }, { name: 'Color', type: 'TEXT', value: 'Black' }]);
      await loadProducts(); notify('Variant added to the database.');
    } catch (e) { if (e.code === 'DUPLICATE_SKU' || /DUPLICATE_SKU/i.test(e.message || '')) setFieldErrors({ sku: 'This SKU is already in use.' }); else if (!mapValidation(e)) setFormError(e); }
    finally { setSaving(false); }
  };

  const renderField = (name, label, props = {}) => <label className="field" key={name}>{label}<input name={name} {...props} aria-invalid={!!fieldErrors[name]} />{fieldErrors[name] && <small className="field-error">{fieldErrors[name]}</small>}</label>;
  const activeCategories = categories.flatMap(category => [category, ...(category.children || [])]);

  if (!token) return <section className="panel"><h3>Sign in to your store account</h3><p className="muted">Live product data is available after signing in with an account that can view products.</p><a className="btn primary" href="#/login">Sign in</a></section>;
  return <>
    <div className="toolbar"><input placeholder="Search product name, code, or SKU" value={query} onChange={e => { setQuery(e.target.value); setPage(1); }}/><select aria-label="Filter category" value={categoryId} onChange={e => { setCategoryId(e.target.value); setPage(1); }}><option value="">All categories</option>{activeCategories.map(c => <option value={c.categoryId} key={c.categoryId}>{c.name}</option>)}</select><select aria-label="Filter status" value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}><option value="ACTIVE">Active</option><option value="INACTIVE">Inactive</option></select>{isOwner && <button className="btn primary" onClick={() => { setFieldErrors({}); setFormError(null); setImagePreview(''); setEditor({ mode: 'new', product: {} }); }}>+ Add product</button>}</div>
    <ErrorMessage error={error}/>{loading ? <SkeletonRows/> : <section className="panel"><div className="table-wrap"><table><thead><tr>{['Product','Product code','Variants','Status','Actions'].map(x=><th key={x}>{x}</th>)}</tr></thead><tbody>{products.length ? products.map(p=><tr key={p.product_id}><td><b>{p.name}</b><small className="block muted">{activeCategories.find(c=>c.categoryId===p.category_id)?.name || ('Category #'+p.category_id)}</small></td><td>{p.product_code}</td><td>{p.variants.length} SKU</td><td><span className={'badge '+(status==='ACTIVE'?'green':'amber')}>{status==='ACTIVE'?'Active':'Inactive'}</span></td><td><div className="actions"><button className="link" onClick={()=>openVariant(p)}>Variants</button>{isOwner&&<><button className="link" onClick={()=>openEdit(p)}>Edit</button><button className="link danger" onClick={()=>changeStatus(p)}>{status==='ACTIVE'?'Deactivate':'Activate'}</button></>}</div></td></tr>) : <tr><td colSpan="5"><div className="empty"><h3>No products found</h3><p>Products for this store will appear here.</p></div></td></tr>}</tbody></table></div><div className="product-pagination"><button className="btn outline" disabled={page===1} onClick={()=>setPage(value=>value-1)}>? Previous</button><span>Page {page}</span><button className="btn outline" disabled={products.length<PAGE_SIZE} onClick={()=>setPage(value=>value+1)}>Next ?</button></div></section>}
    {editor && <div className="overlay" onClick={()=>setEditor(null)}><section className="dialog product-dialog" role="dialog" aria-modal="true" onClick={e=>e.stopPropagation()}><button className="close" onClick={()=>setEditor(null)}>{"\u00d7"}</button>{editor.mode==='variant' ? <><span className="eyebrow">PRODUCT / VARIANTS</span><h2>{editor.product.name}</h2>{formError && <ErrorMessage error={formError}/>}{isOwner&&<form onSubmit={saveVariant}>{renderField('variantName','Variant name',{defaultValue:'Size M - M\u00e0u \u0110en',required:true})}{renderField('sku','SKU (optional)',{defaultValue:'',placeholder:'Leave blank to generate a suggestion'})}{renderField('price','Price',{type:'number',min:'0',step:'0.01',required:true})}<div className="variant-attributes"><div className="section-title"><h3>Variant attributes</h3><button type="button" className="btn outline" onClick={()=>setVariantRows(rows=>[...rows,{name:'',type:'TEXT',value:''}])}>+ Add attribute</button></div>{variantRows.map((row,i)=><div className="attribute-row" key={i}><input name="attributeName" aria-label="Attribute name" placeholder="Attribute name" defaultValue={row.name} required/><select name="attributeType" aria-label="Data type" defaultValue={row.type} onChange={e=>setVariantRows(rows=>rows.map((item,index)=>index===i?{...item,type:e.target.value}:item))}><option value="TEXT">Text</option><option value="NUMBER">Number</option><option value="BOOLEAN">True / false</option></select>{row.type==='BOOLEAN'?<select name="attributeValue" aria-label="Attribute value" defaultValue={String(row.value==='true'||row.value===true)}><option value="true">True</option><option value="false">False</option></select>:<input name="attributeValue" aria-label="Attribute value" type={row.type==='NUMBER'?'number':'text'} defaultValue={row.value} placeholder="Value" required/>}<button type="button" className="link danger" onClick={()=>setVariantRows(rows=>rows.filter((_,index)=>index!==i))}>Remove</button></div>)}</div><ErrorMessage error={formError}/><button className="btn primary" disabled={saving}>{saving?'Saving...':'Save variant'}</button></form>}<h3 className="variant-list-title">Existing variants</h3><div className="table-wrap"><table><thead><tr><th>SKU</th><th>Name</th><th>Price</th><th>Status</th></tr></thead><tbody>{(detail?.variants||[]).map(v=><tr key={v.variant_id}><td>{v.sku}</td><td>{v.variant_name}</td><td>{Number(v.price).toLocaleString()}</td><td>{v.status==='ACTIVE'?'Active':'Inactive'}</td></tr>)}</tbody></table></div></> : <><span className="eyebrow">PRODUCT</span><h2>{editor.mode==='new'?'Add product':'Edit product'}</h2><ErrorMessage error={formError}/><form onSubmit={saveProduct}>{renderField('name','Product name',{defaultValue:editor.product.name||'',maxLength:200,required:true})}<label className="field">Category<select name="categoryId" defaultValue={editor.product.category_id||editor.product.categoryId||''} required aria-invalid={!!fieldErrors.categoryId}><option value="">Choose a category</option>{activeCategories.map(c=><option key={c.categoryId} value={c.categoryId}>{c.name}</option>)}</select>{fieldErrors.categoryId&&<small className="field-error">{fieldErrors.categoryId}</small>}</label>{editor.mode==='new'&&renderField('productCode','Product code (optional)',{maxLength:50})}{renderField('description','Description',{defaultValue:editor.product.description||'',maxLength:16000})}{renderField('imageUrl','Image URL',{type:'url',defaultValue:editor.product.imageUrl||'',placeholder:'https://...' ,onChange:e=>setImagePreview(e.target.value)})}{imagePreview&&<div className="product-image-preview"><img src={imagePreview} alt="Product preview" onError={e=>{e.currentTarget.style.display='none'}}/><small>Image preview</small></div>}<label className="field">Status<select name="status" defaultValue={editor.product.status||'ACTIVE'}><option value="ACTIVE">Active</option><option value="INACTIVE">Inactive</option></select></label><button className="btn primary" disabled={saving}>{saving?'Saving...':editor.mode==='new'?'Create product and add variant':'Save product'}</button></form></>}</section></div>}
  </>;
}
