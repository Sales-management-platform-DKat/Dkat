# POS and sales order test evidence

## Execution

- Command: `npm.cmd --prefix frontend test`
- Result: **28 passed, 0 failed** (9 existing domain/CSV tests and 19 mock API workflow tests).
- Scope: frontend mock API workflows. This is not a live MySQL/backend integration run.

## POS cases

| # | Case | Result |
|---|---|---|
| 1 | Search product by exact SKU | PASS |
| 2 | Reject a quantity above available stock | PASS |
| 3 | Calculate subtotal, discount, and total | PASS |
| 4 | Reject discount greater than subtotal | PASS |
| 5 | Confirm cash payment and deduct inventory | PASS |
| 6 | Reject a second payment confirmation | PASS |
| 7 | Cancel a pending order and release its stock hold | PASS |
| 8 | Restrict order creation to the employee's assigned branch | PASS |
| 9 | Prevent EMPLOYEE from refunding | PASS |
| 10 | Create a guest order without customer details | PASS |
| 11 | Reuse a customer with a duplicate phone number | PASS |
| 12 | Link a selected customer to an order | PASS |

## Sales order cases

| # | Case | Result |
|---|---|---|
| 1 | Filter order list by status and order code | PASS |
| 2 | Open order detail and verify item snapshots | PASS |
| 3 | Cancel a pending order | PASS |
| 4 | Confirm payment for a pending order | PASS |
| 5 | Reject duplicate payment confirmation | PASS |
| 6 | Require refund reason and restore inventory | PASS |
| 7 | Hide refund capability from EMPLOYEE | PASS |
| 8 | Restrict EMPLOYEE order list to assigned branch | PASS |
| 9 | Display guest orders without customer data | PASS |

## Related inventory cases

| Case | Result |
|---|---|
| Import five units and verify on-hand increases by five | PASS |
| Reject export above available stock | PASS |
| Apply stocktake and record an adjustment movement | PASS |

Automated cases live in [live-api-flows.test.js](./live-api-flows.test.js).
