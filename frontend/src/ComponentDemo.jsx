import React, { useState } from 'react';

function ConfirmModal({ open, onClose, onConfirm }) {
  if (!open) return null;
  return <div className="overlay" onClick={onClose}><section className="dialog" role="dialog" aria-modal="true" onClick={e=>e.stopPropagation()}><h2>Confirm action</h2><p>This is the shared confirmation dialog preview.</p><div className="actions"><button className="btn outline" onClick={onClose}>Cancel</button><button className="btn primary" onClick={onConfirm}>Confirm</button></div></section></div>;
}

export default function ComponentDemo({ Table, Badge }) {
  const [confirming, setConfirming] = useState(false);
  const [message, setMessage] = useState('');
  return <>
    <section className="panel"><div className="section-title"><div><span className="eyebrow">ADMIN / COMPONENTS</span><h2>Shared component preview</h2></div><Badge tone="green">ACTIVE</Badge></div><p className="muted">Table, form field, status badge, confirmation dialog, page header, and toast preview.</p></section>
    <section className="panel"><h3>DataTable</h3><Table heads={['SKU','Product','Status']} rows={[[<b>TEE-BLK-M</b>,'Essential Tee',<Badge tone="green">ACTIVE</Badge>],['BAG-NAT-01','Canvas Tote',<Badge tone="amber">INACTIVE</Badge>]]}/></section>
    <section className="panel"><h3>FormField</h3><label className="field">Required name<input placeholder="Enter a name" required/></label><label className="field">Invalid example<input aria-invalid="true" defaultValue=""/><small className="field-error">This field is required.</small></label></section>
    <section className="panel"><h3>ConfirmModal and Toast</h3><div className="actions"><button className="btn outline" onClick={()=>setConfirming(true)}>Preview confirm</button><button className="btn primary" onClick={()=>setMessage('Toast preview is visible.')}>Preview toast</button></div>{message&&<div className="notice green" role="status">{message}<button className="link" onClick={()=>setMessage('')}>Dismiss</button></div>}</section>
    <ConfirmModal open={confirming} onClose={()=>setConfirming(false)} onConfirm={()=>{setConfirming(false);setMessage('Action confirmed.')}}/>
  </>;
}
