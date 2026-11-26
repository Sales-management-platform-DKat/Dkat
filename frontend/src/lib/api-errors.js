// Turns any API/network failure into a short, user-facing Vietnamese message.
// Raw backend text (SQL, stack traces, English internals) is never shown; the
// full error stays available on `error.detail` / the console for developers.

export class ApiError extends Error {
  constructor(message, { status = 0, code = '', detail = null, fieldErrors = {} } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.detail = detail;
    this.fieldErrors = fieldErrors;
  }
}

const STATUS_MESSAGES = {
  0: 'Không thể kết nối đến máy chủ. Kiểm tra mạng và thử lại.',
  400: 'Yêu cầu chưa hợp lệ.',
  401: 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.',
  403: 'Bạn không có quyền thực hiện thao tác này.',
  404: 'Không tìm thấy dữ liệu yêu cầu.',
  409: 'Dữ liệu đã thay đổi hoặc bị trùng. Vui lòng kiểm tra lại.',
  413: 'File quá lớn.',
  422: 'Dữ liệu nhập không hợp lệ.',
  429: 'Bạn thao tác quá nhanh. Vui lòng thử lại sau ít phút.',
  500: 'Máy chủ gặp sự cố. Vui lòng thử lại sau.',
  502: 'Không thể kết nối đến máy chủ. Vui lòng thử lại sau.',
  503: 'Không thể kết nối đến máy chủ. Vui lòng thử lại sau.',
  504: 'Máy chủ phản hồi quá chậm. Vui lòng thử lại.',
};

const CODE_MESSAGES = {
  INSUFFICIENT_STOCK: 'Không đủ tồn kho khả dụng cho thao tác này.',
  OUT_OF_STOCK: 'Sản phẩm không đủ hàng tại chi nhánh.',
  STOCK_BELOW_RESERVED: 'Số lượng kiểm kê thấp hơn số lượng đang giữ cho đơn đặt trước.',
  STOCK_LIMIT_EXCEEDED: 'Tồn kho vượt giới hạn cho phép.',
  VARIANT_NOT_FOUND: 'Không tìm thấy biến thể sản phẩm.',
  VARIANT_IN_STOCK: 'Sản phẩm vẫn còn hàng, hãy bán trực tiếp thay vì đặt trước.',
  VARIANT_INACTIVE: 'Sản phẩm hoặc biến thể đã ngừng kinh doanh.',
  BRANCH_NOT_FOUND: 'Không tìm thấy chi nhánh đang hoạt động.',
  INVALID_BRANCH_ASSIGNMENT: 'Chi nhánh được chọn không hợp lệ hoặc đã ngừng hoạt động.',
  INVALID_STOCK_CSV: 'File nhập kho còn dòng lỗi. Vui lòng sửa và thử lại.',
  DUPLICATE_STOCK_IMPORT: 'Dữ liệu này đã được nhập trong 24 giờ qua.',
  CSV_FILE_TOO_LARGE: 'File quá lớn (tối đa 5 MB).',
  ORDER_NOT_PENDING: 'Đơn hàng không còn ở trạng thái chờ thanh toán.',
  DUPLICATE_SKU: 'SKU đã tồn tại trong cửa hàng.',
  RATE_LIMITED: 'Bạn thao tác quá nhanh. Vui lòng thử lại sau ít phút.',
};

// Known English messages from older endpoints.
const TEXT_MESSAGES = [
  [/product code already exists/i, 'Mã sản phẩm đã tồn tại trong cửa hàng.'],
  [/duplicate_sku|sku already exists/i, 'SKU đã tồn tại trong cửa hàng.'],
  [/category not found/i, 'Không tìm thấy danh mục.'],
  [/product not found/i, 'Không tìm thấy sản phẩm.'],
  [/attribute not found/i, 'Không tìm thấy thuộc tính.'],
  [/category is inactive/i, 'Danh mục đang ngừng hoạt động.'],
  [/category.*(already exists|duplicate)/i, 'Danh mục đã tồn tại.'],
  [/cycle/i, 'Không thể chọn danh mục con làm danh mục cha.'],
  [/database unavailable/i, STATUS_MESSAGES[503]],
];

const FIELD_LABELS = {
  name: 'Tên', fullName: 'Họ tên', full_name: 'Họ tên', phone: 'Số điện thoại', email: 'Email',
  address: 'Địa chỉ', branchCode: 'Mã chi nhánh', branch_code: 'Mã chi nhánh', username: 'Tên đăng nhập',
  password: 'Mật khẩu', price: 'Giá bán', costPrice: 'Giá vốn', sku: 'SKU', quantity: 'Số lượng',
  categoryId: 'Danh mục', variantName: 'Tên biến thể', reason: 'Lý do', note: 'Ghi chú',
};

const VIETNAMESE = /[À-ỹ]/;

function fieldMessage(issue) {
  const raw = String(issue?.msg || issue?.reason || issue?.message || '').replace(/^Value error, /, '');
  if (VIETNAMESE.test(raw)) return raw;
  const type = issue?.type || '';
  if (type === 'missing' || /field required/i.test(raw)) return 'Vui lòng nhập thông tin này.';
  if (type.startsWith('string_too_short')) return 'Vui lòng nhập thông tin này.';
  if (type.startsWith('string_too_long')) return 'Nội dung quá dài.';
  if (type.startsWith('string_pattern') || /pattern|valid email/i.test(raw)) return 'Định dạng chưa đúng.';
  if (/greater than|less than|ge=|le=/i.test(raw) || type.startsWith('greater') || type.startsWith('less')) return 'Giá trị nằm ngoài khoảng cho phép.';
  if (/integer|number|decimal/i.test(raw) || type.includes('parsing')) return 'Vui lòng nhập số hợp lệ.';
  return 'Giá trị chưa hợp lệ.';
}

function fieldName(issue) {
  if (issue?.field) return String(issue.field).split('.').pop();
  const loc = Array.isArray(issue?.loc) ? issue.loc.filter((part) => part !== 'body') : [];
  return loc.length ? String(loc[loc.length - 1]) : '';
}

export function errorFromResponse(status, data) {
  const detail = data?.detail ?? data;
  const fieldErrors = {};
  let message = '';
  let code = '';
  const issues = Array.isArray(detail) ? detail : Array.isArray(data?.details) ? data.details : [];
  for (const issue of issues) {
    const name = fieldName(issue);
    if (name && !fieldErrors[name]) fieldErrors[name] = fieldMessage(issue);
  }
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    code = detail.code || '';
    message = detail.message || '';
  } else if (data && typeof data === 'object' && data.code) {
    code = data.code;
    message = data.message || '';
  }
  if (typeof detail === 'string') message = detail;
  if (code && CODE_MESSAGES[code] && !VIETNAMESE.test(message)) message = CODE_MESSAGES[code];
  if (message && !VIETNAMESE.test(message)) {
    message = TEXT_MESSAGES.find(([pattern]) => pattern.test(message))?.[1] || '';
  }
  if (!message && Object.keys(fieldErrors).length) {
    const [name, text] = Object.entries(fieldErrors)[0];
    message = FIELD_LABELS[name] ? `${FIELD_LABELS[name]}: ${text}` : STATUS_MESSAGES[422];
  }
  if (!message || status >= 500) message = STATUS_MESSAGES[status] || STATUS_MESSAGES[status >= 500 ? 500 : 400];
  return new ApiError(message, { status, code, detail, fieldErrors });
}

export function networkError(cause) {
  const error = new ApiError(STATUS_MESSAGES[0], { status: 0, code: 'NETWORK' });
  error.cause = cause;
  return error;
}

// Message for any thrown value (ApiError, Error, string).
export function friendlyMessage(error, fallback = 'Đã xảy ra sự cố khi xử lý yêu cầu. Vui lòng thử lại.') {
  if (!error) return fallback;
  if (error instanceof ApiError) return error.message;
  const text = typeof error === 'string' ? error : error.message || '';
  if (!text || /failed to fetch|networkerror|load failed/i.test(text)) return text ? STATUS_MESSAGES[0] : fallback;
  return VIETNAMESE.test(text) ? text : fallback;
}

export function fieldErrorsOf(error) {
  return error?.fieldErrors || {};
}
