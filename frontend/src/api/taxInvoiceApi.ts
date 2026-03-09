// frontend/src/api/taxInvoiceApi.ts
import apiClient from './client';
import { API } from './endpoints';
import type { TaxInvoiceListResponse, OcrBusinessResult } from '../types/taxInvoice';

/** 관리자: 세금계산서 목록 */
export async function fetchTaxInvoices(params?: {
  status?: string;
  seller_id?: number;
  date_from?: string;
  date_to?: string;
  skip?: number;
  limit?: number;
}): Promise<TaxInvoiceListResponse> {
  const { data } = await apiClient.get(API.TAX_INVOICES.LIST, { params });
  return data;
}

/** 판매자: 내 세금계산서 목록 */
export async function fetchMyTaxInvoices(sellerId: number, skip = 0, limit = 50): Promise<TaxInvoiceListResponse> {
  const { data } = await apiClient.get(API.TAX_INVOICES.SELLER_ME, {
    params: { seller_id: sellerId, skip, limit },
  });
  return data;
}

/** 수동 생성 (admin) */
export async function generateTaxInvoice(settlementId: number) {
  const { data } = await apiClient.post(API.TAX_INVOICES.GENERATE, { settlement_id: settlementId });
  return data;
}

/** 판매자 확인 */
export async function confirmTaxInvoice(invoiceId: number, sellerId: number) {
  const { data } = await apiClient.post(API.TAX_INVOICES.CONFIRM(invoiceId), null, {
    params: { seller_id: sellerId },
  });
  return data;
}

/** 단건 발행 (admin) */
export async function issueTaxInvoice(invoiceId: number) {
  const { data } = await apiClient.post(API.TAX_INVOICES.ISSUE(invoiceId));
  return data;
}

/** 일괄 발행 (admin) */
export async function batchIssueTaxInvoices(invoiceIds: number[]) {
  const { data } = await apiClient.post(API.TAX_INVOICES.BATCH_ISSUE, { invoice_ids: invoiceIds });
  return data;
}

/** 취소 (admin) */
export async function cancelTaxInvoice(invoiceId: number) {
  const { data } = await apiClient.post(API.TAX_INVOICES.CANCEL(invoiceId));
  return data;
}

/** ECOUNT 엑셀 다운로드 */
export async function exportEcountXlsx(invoiceIds: number[]) {
  const { data } = await apiClient.get(API.TAX_INVOICES.EXPORT_ECOUNT, {
    params: { invoice_ids: invoiceIds.join(',') },
    responseType: 'blob',
  });
  return data;
}

/** 사업자등록증 OCR */
export async function ocrBusinessRegistration(file: File): Promise<OcrBusinessResult> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await apiClient.post(API.SELLER_BUSINESS.OCR, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data.data;
}

/** 사업자 정보 수정 */
export async function updateBusinessInfo(sellerId: number, body: Record<string, string>) {
  const { data } = await apiClient.patch(API.SELLER_BUSINESS.UPDATE(sellerId), body);
  return data;
}
