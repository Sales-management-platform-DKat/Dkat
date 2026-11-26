// Sample store content for the in-browser demo (data, not UI copy: names stay as entered).
export const DEMO_STORE_NAME = 'DKat Fashion (Demo)';
export const DEMO_ATTRIBUTES = { color: 'Màu sắc', size: 'Kích thước' };

export const DEMO_BRANCHES = [
  { id: 1, branchCode: 'CN01', name: 'DKat Quận 1', address: '12 Lê Lợi, Quận 1, TP.HCM', phone: '0901000001', ageDays: 60 },
  { id: 2, branchCode: 'CN02', name: 'DKat Cầu Giấy', address: '88 Xuân Thủy, Cầu Giấy, Hà Nội', phone: '0901000002', ageDays: 30 },
];

export const DEMO_USERS = [
  { id: 1, username: 'demoowner', full_name: 'Chủ cửa hàng Demo', email: 'owner@demo.dkat', phone: null, role: 'OWNER', branchIds: [], ageDays: 60 },
  { id: 2, username: 'demomanager', full_name: 'Quản lý Demo', email: null, phone: '0902000002', role: 'MANAGER', branchIds: [1], ageDays: 40 },
  { id: 3, username: 'demostaff', full_name: 'Nhân viên Demo', email: null, phone: '0903000003', role: 'EMPLOYEE', branchIds: [1], ageDays: 20 },
];

export const DEMO_CATEGORIES = [
  { categoryId: 1, parentCategoryId: null, name: 'Áo', description: 'Áo sơ mi, áo thun', status: 'ACTIVE' },
  { categoryId: 2, parentCategoryId: null, name: 'Quần', description: null, status: 'ACTIVE' },
  { categoryId: 3, parentCategoryId: null, name: 'Phụ kiện', description: null, status: 'ACTIVE' },
];

export const DEMO_CUSTOMERS = [
  { customerId: 1, fullName: 'Nguyễn Minh Anh', phone: '0912345678', email: 'minhanh@example.vn', address: '5 Nguyễn Huệ, Quận 1', note: null },
  { customerId: 2, fullName: 'Trần Gia Hân', phone: '0987654321', email: null, address: '20 Trần Duy Hưng, Hà Nội', note: 'Khách thân thiết' },
];

// [productId, name, code prefix, categoryId, [[color, size, price, stock at branch 1]]]
export const DEMO_CATALOG = [
  [1, 'Áo sơ mi Oxford', 'ASM', 1, [['Trắng', 'M', 350000, 12], ['Trắng', 'L', 350000, 0], ['Xanh', 'M', 360000, 6]]],
  [2, 'Áo thun Basic', 'ATB', 1, [['Đen', 'M', 180000, 25], ['Be', 'L', 180000, 0]]],
  [3, 'Quần jean Slim', 'QJS', 2, [['Xanh đậm', '30', 520000, 8]]],
  [4, 'Túi tote canvas', 'TTC', 3, [['Kem', 'Free', 150000, 0], ['Đen', 'Free', 150000, 4]]],
];

export const demoDescription = (name) => `${name} – sản phẩm mẫu của bản demo.`;
