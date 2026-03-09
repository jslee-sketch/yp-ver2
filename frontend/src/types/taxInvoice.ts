// frontend/src/types/taxInvoice.ts

export type TaxInvoiceStatus = 'PENDING' | 'CONFIRMED' | 'ISSUED' | 'CANCELLED';

export interface TaxInvoice {
  id: number;
  invoice_number: string;
  status: TaxInvoiceStatus;
  supplier_business_name: string;
  supplier_business_number: string;
  supplier_representative: string;
  supplier_address: string;
  supplier_email?: string;
  recipient_type: 'seller' | 'actuator';
  recipient_id: number;
  recipient_business_name?: string;
  recipient_business_number?: string;
  recipient_representative?: string;
  recipient_address?: string;
  recipient_email?: string;
  recipient_business_type?: string;
  recipient_business_item?: string;
  settlement_id: number;
  total_amount: number;
  supply_amount: number;
  tax_amount: number;
  issued_at?: string;
  confirmed_at?: string;
  cancelled_at?: string;
  created_at?: string;
  notes?: string;
}

export interface TaxInvoiceListResponse {
  total: number;
  items: TaxInvoice[];
}

export interface OcrBusinessResult {
  business_name: string;
  business_number: string;
  representative_name: string;
  address: string;
  business_type: string;
  business_item: string;
}
