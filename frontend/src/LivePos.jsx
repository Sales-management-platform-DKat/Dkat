import React, { useEffect, useMemo, useRef, useState } from 'react';
import { apiRequest } from './auth-client';
import { useCurrentBranch } from './branches/BranchContext';

export default function LivePos({ token, branchId: branchProp, notify }) {
  const branchContext = useCurrentBranch();
  const branchId = branchProp || branchContext.branchId;
  const [products, setProducts] = useState([]);
  const [inventory, setInventory] = useState([]);
  const [query, setQuery] = useState('');
  const [cart, setCart] = useState(() => { try { return JSON.parse(localStorage.getItem(`dkat-cart-${branchId}`) || '[]'); } catch { return []; } });
  const [discount, setDiscount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [outOfStock, setOutOfStock] = useState([]);
  const [chooseProduct, setChooseProduct] = useState(null);
  const [createdOrder, setCreatedOrder] = useState(null);
  const [paymentMethod, setPaymentMethod] = useState('CASH');
  const [cashReceived, setCashReceived] = useState('');
  const [paymentSaving, setPaymentSaving] = useState(false);
  const [customerSearch, setCustomerSearch] = useState('');
  const [customerResults, setCustomerResults] = useState([]);
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [newCustomerOpen, setNewCustomerOpen] = useState(false);
  const searchRef = useRef(null);
  const currentBranch = branchContext.branches.find(b => String(b.id ?? b.branchId) === String(branchId));

  useEffect(() => { try { setCart(JSON.parse(localStorage.getItem(`dkat-cart-${branchId}`) || '[]')); } catch { setCart([]); } }, [branchId]);
  useEffect(() => { localStorage.setItem(`dkat-cart-${branchId}`, JSON.stringify(cart)); }, [cart, branchId]);
  useEffect(() => {
    let active = true; setLoading(true); setError(null);
    const timer = setTimeout(() => {
      const params = new URLSearchParams({ status: 'ACTIVE', page: '1', size: '100' }); if (query.trim()) params.set('keyword', query.trim());
      const inventoryParams = new URLSearchParams({ page: '1', size: '100' });
      if (branchId && branchId !== 'all') inventoryParams.set('branchId', String(branchId));
      Promise.all([apiRequest(`/products?${params}`, { token }), apiRequest(`/inventory?${inventoryParams}`, { token })])
        .then(([list, stocks]) => { if (active) { setProducts(list); setInventory(stocks); } })
        .catch(e => { if (active) setError(e); })
        .finally(() => { if (active) setLoading(false); });
    }, query ? 250 : 0);
    return () => { active = false; clearTimeout(timer); };
  }, [token, branchId, query]);
  useEffect(() => { searchRef.current?.focus(); }, []);
  useEffect(() => { if(customerSearch.trim().length<2){setCustomerResults([]);return}let active=true;const timer=setTimeout(()=>apiRequest(`/customers/quick-search?q=${encodeURIComponent(customerSearch.trim())}`,{token}).then(rows=>{if(active)setCustomerResults(rows)}).catch(()=>{if(active)setCustomerResults([])}),200);return()=>{active=false;clearTimeout(timer)}; },[customerSearch,token]);
  useEffect(() => { const key = event => { if (event.key === 'F2') { event.preventDefault(); searchRef.current?.focus(); searchRef.current?.select(); } }; window.addEventListener('keydown', key); return () => window.removeEventListener('keydown', key); }, []);

  const stockFor = (variantId) => inventory.find(item => item.variantId === variantId && (branchId === 'all' || String(item.branchId) === String(branchId)));
  const visibleProducts = useMemo(() => products.filter(p => !query || [p.name,p.product_code,...p.variants.map(v=>v.sku)].some(x=>x.toLowerCase().includes(query.toLowerCase()))), [products,query]);
  const subtotal = cart.reduce((sum, item) => sum + item.price * item.quantity, 0);
  const total = subtotal - Math.min(Number(discount) || 0, subtotal);

  const add = (product, variant) => {
    const stock = stockFor(variant.variant_id);
    if (!stock || stock.available <= 0 || outOfStock.includes(variant.variant_id)) return;
    setCart(items => {
      const current = items.find(item => item.variantId === variant.variant_id)?.quantity || 0;
      if (current >= stock.available) { notify('Cart quantity exceeds available stock.', 'error'); return items; }
      return current ? items.map(item => item.variantId === variant.variant_id ? { ...item, quantity: item.quantity + 1 } : item) : [...items, { variantId: variant.variant_id, name: product.name, sku: variant.sku, price: Number(variant.price), quantity: 1 }];
    });
  };
  const setQuantity = (variantId, quantity) => {
    const stock = stockFor(variantId);
    if (quantity > (stock?.available || 0)) { notify('Cart quantity exceeds available stock.', 'error'); return; }
    setCart(items => quantity < 1 ? items.filter(item => item.variantId !== variantId) : items.map(item => item.variantId === variantId ? { ...item, quantity } : item));
  };
  const handleSearchKeyDown = (event) => {
    if (event.key !== 'Enter') return;
    const term = query.trim().toLowerCase();
    const product = products.find(p => p.product_code?.toLowerCase() === term || p.variants.some(v => v.sku?.toLowerCase() === term || v.barcode?.toLowerCase() === term));
    if (!product) return;
    const variant = product.variants.find(v => v.sku?.toLowerCase() === term || v.barcode?.toLowerCase() === term);
    if (variant) add(product, variant);
    else if (product.variants.length === 1) add(product, product.variants[0]);
    else setChooseProduct(product);
    setQuery('');
  };

  const submit = async () => {
    if (!cart.length || !branchId || branchId === 'all') return;
    if (Number(discount) > subtotal) { notify('Discount cannot exceed the subtotal.', 'error'); return; }
    setSaving(true); setError(null); setOutOfStock([]);
    try {
      const order = await apiRequest('/sales-orders', { method: 'POST', token, body: JSON.stringify({ branchId: Number(branchId), customerId:selectedCustomer?.customerId||null, items: cart.map(item => ({ variantId: item.variantId, quantity: item.quantity })), discountAmount: Number(discount) || 0 }) });
      setCreatedOrder(order); setPaymentMethod('CASH'); setCashReceived(''); setCart([]); setDiscount(0); setSelectedCustomer(null); setCustomerSearch('');
    } catch (e) {
      setError(e);
      if (e.code === 'OUT_OF_STOCK' && e.details?.variantId) setOutOfStock(items => [...items, e.details.variantId]);
      notify(e.message, 'error');
    } finally { setSaving(false); }
  };

  const confirmPayment = async () => {
    if (!createdOrder || paymentSaving) return;
    if (paymentMethod === 'CASH' && Number(cashReceived) < Number(createdOrder.totalAmount)) { notify('Cash received must cover the order total.', 'error'); return; }
    setPaymentSaving(true);
    try {
      const paid = await apiRequest(`/sales-orders/${createdOrder.salesOrderId}/confirm-payment`, { method:'POST', token, body:JSON.stringify({paymentMethod,amountTendered:paymentMethod==='CASH'?Number(cashReceived):null}) });
      setCreatedOrder(paid); setInventory(current=>current.map(item=>{const sold=paid.items?.find(line=>line.variantId===item.variantId);return sold&&String(item.branchId)===String(branchId)?{...item,quantity:item.quantity-sold.quantity,available:item.available-sold.quantity}:item}));
      notify(`Payment confirmed for ${paid.orderCode}.`);
    } catch (e) { setError(e); notify(e.status===409?`409: ${e.message}`:e.message,'error'); }
    finally { setPaymentSaving(false); }
  };
  const cancelOrder = async () => {
    if (!createdOrder || paymentSaving || !window.confirm(`Cancel pending order ${createdOrder.orderCode}?`)) return;
    setPaymentSaving(true);
    try { await apiRequest(`/sales-orders/${createdOrder.salesOrderId}/cancel`,{method:'POST',token}); setCreatedOrder(null); notify('Pending order cancelled.'); }
    catch(e){notify(e.message,'error')} finally{setPaymentSaving(false)}
  };
  const createCustomer = async event => { event.preventDefault();const form=new FormData(event.currentTarget);try{const customer=await apiRequest('/customers',{method:'POST',token,body:JSON.stringify({fullName:String(form.get('fullName')||'').trim(),phone:String(form.get('phone')||'').trim()||null,email:String(form.get('email')||'').trim()||null,address:String(form.get('address')||'').trim()||null})});setSelectedCustomer(customer);setCustomerSearch(customer.fullName);setNewCustomerOpen(false);notify('Customer saved.')}catch(e){notify(e.message,'error')} };

  return <div className="pos-page"><div className="section-title pos-branch-heading"><h2>POS · {currentBranch?.name || (branchId==='all'?'All branches':'Selected branch')}</h2><small>Press F2 to search · scan a SKU and press Enter</small></div><div className="pos-layout"><section><div className="toolbar"><input ref={searchRef} placeholder="Search product, SKU, or barcode" value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={handleSearchKeyDown}/></div>
    {branchId==='all'&&<div className="notice amber">Select a specific branch before creating a sale.</div>}{error&&<div className="notice amber" role="alert">{error.message}</div>}
    {loading?<div className="panel product-skeleton" aria-busy="true">{[0,1,2].map(i=><div className="skeleton-row" key={i}><i/><i/><i/></div>)}</div>:<div className="pos-products">{visibleProducts.map(product=><button className="pos-card" key={product.product_id} onClick={()=>product.variants.length>1?setChooseProduct(product):product.variants[0]&&add(product,product.variants[0])}><h3>{product.name}</h3><small>{product.product_code}</small>{product.variants.length===1&&<><b>{product.variants[0].sku} · {Number(product.variants[0].price).toLocaleString()}</b><small>Available: {stockFor(product.variants[0].variant_id)?.available||0}</small></>}</button>)}</div>}
    {chooseProduct&&<div className="overlay" onClick={()=>setChooseProduct(null)}><section className="dialog" role="dialog" aria-modal="true" onClick={e=>e.stopPropagation()}><button className="close" onClick={()=>setChooseProduct(null)}>×</button><h2>Choose variant · {chooseProduct.name}</h2>{chooseProduct.variants.map(variant=>{const stock=stockFor(variant.variant_id),disabled=!stock||stock.available<=0||outOfStock.includes(variant.variant_id);return <button key={variant.variant_id} className="variant-choice" disabled={disabled} onClick={()=>{add(chooseProduct,variant);setChooseProduct(null)}}><span><b>{variant.variant_name}</b><small>{variant.sku}</small></span><span>{Number(variant.price).toLocaleString()} · {disabled?'Out of stock':`Available ${stock.available}`}</span></button>})}</section></div>}
  </section><aside className="panel checkout"><div className="section-title"><h3>Cart</h3><span>{cart.length} SKU</span></div><label className="field">Customer (optional)<input placeholder={selectedCustomer?.fullName||'Guest customer'} value={customerSearch} onChange={e=>{setCustomerSearch(e.target.value);setSelectedCustomer(null)}}/><small className="muted">Leave empty for a guest sale.</small></label>{customerResults.length>0&&<div className="customer-suggestions">{customerResults.map(customer=><button type="button" className="link" key={customer.customerId} onClick={()=>{setSelectedCustomer(customer);setCustomerSearch(customer.fullName);setCustomerResults([])}}>{customer.fullName} {customer.phone&&`· ${customer.phone}`}</button>)}</div>}<button type="button" className="link" onClick={()=>setNewCustomerOpen(true)}>+ Quick add customer</button>
    {cart.length?cart.map(item=><div className={'cart-row '+(outOfStock.includes(item.variantId)?'stock-error':'')} key={item.variantId}><b>{item.name}</b><small>{item.sku} · {Number(item.price).toLocaleString()}</small><div className="split"><div className="stepper"><button onClick={()=>setQuantity(item.variantId,item.quantity-1)}>−</button><span>{item.quantity}</span><button onClick={()=>setQuantity(item.variantId,item.quantity+1)}>+</button><button onClick={()=>setQuantity(item.variantId,0)} aria-label="Remove item">×</button></div><b>{(item.price*item.quantity).toLocaleString()}</b></div></div>):<div className="empty">Choose a product to begin.</div>}
    <label className="field">Discount amount<input type="number" min="0" max={subtotal} value={discount} onChange={e=>setDiscount(Number(e.target.value))}/></label>
    <div className="total"><span>Subtotal</span><b>{subtotal.toLocaleString()}</b><span>Total</span><strong>{total.toLocaleString()}</strong></div>
    <button className="btn primary" disabled={!cart.length||saving||branchId==='all'} onClick={submit}>{saving?'Creating order…':'Create order'}</button>
    {createdOrder&&<div className="notice green" role="status">{createdOrder.orderCode} · {createdOrder.status} · {Number(createdOrder.totalAmount).toLocaleString()}</div>}
  </aside></div>{newCustomerOpen&&<div className="overlay" onClick={()=>setNewCustomerOpen(false)}><form className="dialog" onSubmit={createCustomer} onClick={e=>e.stopPropagation()}><button type="button" className="close" onClick={()=>setNewCustomerOpen(false)}>×</button><h2>Quick add customer</h2><label className="field">Name<input name="fullName" required maxLength="150"/></label><label className="field">Phone<input name="phone" maxLength="20"/></label><label className="field">Email<input name="email" type="email" maxLength="255"/></label><label className="field">Address<textarea name="address" maxLength="500"/></label><button className="btn primary">Save customer</button></form></div>}{createdOrder?.status==='PENDING'&&<div className="overlay"><section className="dialog" role="dialog" aria-modal="true"><span className="eyebrow">ORDER / PAYMENT</span><h2>Confirm payment</h2><p><b>{createdOrder.orderCode}</b> · Total {Number(createdOrder.totalAmount).toLocaleString()}</p><label className="field">Payment method<select value={paymentMethod} onChange={e=>setPaymentMethod(e.target.value)}>{[['CASH','Cash'],['BANK_TRANSFER','Bank transfer'],['CARD','Card'],['OTHER','Other']].map(([v,l])=><option value={v} key={v}>{l}</option>)}</select></label>{paymentMethod==='CASH'&&<><label className="field">Cash received<input type="number" min={createdOrder.totalAmount} step="1" value={cashReceived} onChange={e=>setCashReceived(e.target.value)}/></label><div className="split"><span>Change due</span><b>{Math.max(0,Number(cashReceived||0)-Number(createdOrder.totalAmount)).toLocaleString()}</b></div></>}<div className="notice amber">Confirm only after checking that payment was received outside this system. Bank payments are not verified automatically.</div><div className="actions"><button className="btn outline" disabled={paymentSaving} onClick={cancelOrder}>Cancel order</button><button className="btn primary" disabled={paymentSaving||(paymentMethod==='CASH'&&Number(cashReceived)<Number(createdOrder.totalAmount))} onClick={confirmPayment}>{paymentSaving?'Processing…':'Confirm paid'}</button></div></section></div>}</div>;
}
