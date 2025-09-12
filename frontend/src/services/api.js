import { API_BASE_URL } from '../lib/constants';

// Helper function for API calls
const apiCall = async (endpoint, options = {}) => {
  const url = `${API_BASE_URL}${endpoint}`;
  
  const defaultHeaders = {};
  // Only set JSON content-type if body is not FormData
  const isFormData = options && options.body && typeof FormData !== 'undefined' && options.body instanceof FormData;
  if (!isFormData) {
    defaultHeaders['Content-Type'] = 'application/json';
  }

  const defaultOptions = {
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  };

  try {
    const response = await fetch(url, { ...defaultOptions, ...options });
    if (!response.ok) {
      // Try to parse error message if possible
      let message = `API call failed: ${response.status} ${response.statusText}`;
      try { const data = await response.json(); if (data && (data.error || data.message)) { message = data.error || data.message; } } catch (_) {}
      throw new Error(message);
    }
    // Some upload endpoints may return JSON; assume JSON here
    return await response.json();
  } catch (error) {
    console.error('API call error:', error);
    throw error;
  }
};

// Marketplace APIs
export const marketplaceAPI = {
  // Get all marketplaces
  getMarketplaces: () => apiCall('/marketplace/marketplaces'),
  
  // Get vendors (global)
  getVendors: () => apiCall('/vendor/vendors'),
  
  // Get all stores (summary)
  getStores: (params = {}) => {
    const queryParams = new URLSearchParams();
    if (params.marketplace_id) queryParams.append('marketplace_id', params.marketplace_id);
    if (params.active_only !== undefined) queryParams.append('active_only', params.active_only);
    
    const queryString = queryParams.toString();
    return apiCall(`/marketplace/stores${queryString ? `?${queryString}` : ''}`);
  },
  
  // Get single store (full vendor settings)
  getStore: (storeId) => apiCall(`/marketplace/stores/${storeId}`),
  
  // Create store
  createStore: (storeData) => apiCall('/marketplace/stores', {
    method: 'POST',
    body: JSON.stringify(storeData),
  }),
  
  // Update store
  updateStore: (storeId, storeData) => apiCall(`/marketplace/stores/${storeId}`, {
    method: 'PUT',
    body: JSON.stringify(storeData),
  }),
  
  // Duplicate store
  duplicateStore: (storeId, data) => apiCall(`/marketplace/stores/${storeId}/duplicate`, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  
  // Set active flag only
  setStoreActive: (storeId, isActive) => apiCall(`/marketplace/stores/${storeId}/active`, {
    method: 'PUT',
    body: JSON.stringify({ is_active: isActive }),
  }),
  
  // Delete store
  deleteStore: (storeId) => apiCall(`/marketplace/stores/${storeId}`, {
    method: 'DELETE',
  }),

  // Upload MyDeal price template
  uploadMyDealPriceTemplate: async (file) => {
    const form = new FormData();
    form.append('file', file);
    return apiCall('/marketplace/mydeal/templates/price', {
      method: 'POST',
      body: form,
    });
  },

  // Upload MyDeal inventory template
  uploadMyDealInventoryTemplate: async (file) => {
    const form = new FormData();
    form.append('file', file);
    return apiCall('/marketplace/mydeal/templates/inventory', {
      method: 'POST',
      body: form,
    });
  },
};

// Helper function to transform frontend data to API format (vendor arrays)
export const transformStoreDataForAPI = (storeInfo, priceSettingsByVendor, inventorySettingsByVendor, mydealSettingsState) => {
  const payload = {
    name: storeInfo.storeName,
    marketplace_id: parseInt(storeInfo.marketplace),
    api_key_enc: storeInfo.apiKey || "",
    price_settings_by_vendor: (priceSettingsByVendor || []).map(v => ({
      vendor_id: v.vendorId,
      purchase_tax_percentage: parseFloat(v.purchaseTax) || 0,
      marketplace_fees_percentage: parseFloat(v.marketplaceFees) || 0,
      price_ranges: (v.priceRanges || []).map(range => ({
        from_value: parseFloat(range.from) || 0,
        to_value: range.to || "MAX",
        margin_percentage: parseFloat(range.margin) || 0,
        minimum_margin_cents: ((parseInt(range.minimumMargin) || 0) * 100),
        dont_pay_discount_percentage: (range.dontPayDiscountPercentage !== undefined && range.dontPayDiscountPercentage !== null)
          ? parseFloat(range.dontPayDiscountPercentage)
          : 10,
      }))
    })),
    inventory_settings_by_vendor: (inventorySettingsByVendor || []).map(v => ({
      vendor_id: v.vendorId,
      inventory_ranges: (v.priceRanges || []).map(range => ({
        from_value: parseFloat(range.from) || 0,
        to_value: range.to || "MAX",
        multiplier: parseFloat(range.multipliedWith) || 0
      }))
    }))
  };

  // Attach MyDeal settings if marketplace is MyDeal
  if (storeInfo.marketplaceName === 'MyDeal' || storeInfo.marketplaceCode === 'MyDeal' || mydealSettingsState) {
    payload.settings = payload.settings || {};
    payload.settings.mydeal = {
      price_template_upload_id: mydealSettingsState?.priceTemplateUploadId || null,
      inventory_template_upload_id: mydealSettingsState?.inventoryTemplateUploadId || null,
    };
  }

  return payload;
};

// Helper function to transform API data to frontend format (vendor arrays)
export const transformStoreDataForFrontend = (apiStoreData) => {
  return {
    id: apiStoreData.id,
    name: apiStoreData.name,
    marketplace: apiStoreData.marketplace.name,
    marketplace_id: apiStoreData.marketplace.id,
    is_active: apiStoreData.is_active,
    created_at: apiStoreData.created_at,
    storeInfo: {
      storeName: apiStoreData.name,
      marketplace: apiStoreData.marketplace.id.toString(),
      apiKey: apiStoreData.api_key_enc,
      marketplaceName: apiStoreData.marketplace.name,
      marketplaceCode: apiStoreData.marketplace.code,
    },
    priceSettingsByVendor: (apiStoreData.price_settings_by_vendor || []).map(s => ({
      vendorId: s.vendor_id,
      purchaseTax: s.purchase_tax_percentage.toString(),
      marketplaceFees: s.marketplace_fees_percentage.toString(),
      priceRanges: (s.price_ranges || []).map(range => ({
        from: range.from_value.toString(),
        to: range.to_value,
        margin: range.margin_percentage.toString(),
        minimumMargin: ((range.minimum_margin_cents || 0) / 100).toString(),
        dontPayDiscountPercentage: (range.dont_pay_discount_percentage ?? 10).toString(),
      }))
    })),
    inventorySettingsByVendor: (apiStoreData.inventory_settings_by_vendor || []).map(s => ({
      vendorId: s.vendor_id,
      priceRanges: (s.inventory_ranges || []).map(range => ({
        from: range.from_value.toString(),
        to: range.to_value,
        multipliedWith: range.multiplier.toString()
      }))
    })),
    settings: apiStoreData.settings || {},
    mydealSettings: (apiStoreData.settings && apiStoreData.settings.mydeal) ? {
      priceTemplateUploadId: apiStoreData.settings.mydeal.price_template_upload_id || null,
      inventoryTemplateUploadId: apiStoreData.settings.mydeal.inventory_template_upload_id || null,
    } : null,
  };
}; 