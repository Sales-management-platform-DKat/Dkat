import {test} from 'node:test';
import assert from 'node:assert/strict';
import {importProducts} from '../src/csv.js';
import {seed} from '../src/seed.js';
test('CSV không lưu một phần nếu một dòng sai',()=>{const s=seed(),len=s.variants.length;assert.throws(()=>importProducts(s,'name,sku,category,color,size,price\nÁo mới,NEW1,Áo,Đen,M,120000\nÁo lỗi,AT-BLK-M,Áo,Đen,M,100'));assert.equal(s.variants.length,len)});
test('CSV đọc được tên có dấu phẩy trong nháy',()=>{const s=seed();assert.equal(importProducts(s,'name,sku,category,color,size,price\n"Áo, bản mới",NEW2,Áo,Đen,M,120000'),1);assert.equal(s.variants.at(-1).name,'Áo, bản mới')});
