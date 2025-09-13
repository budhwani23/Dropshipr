import { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { dashboardAPI, marketplaceAPI, exportAPI } from "../services/api";
import { Package, Store as StoreIcon, Users, AlertTriangle, Upload, RefreshCw, Download } from "lucide-react";

const ALL_VALUE = "__ALL__";

export default function Dashboard() {
  const [loading, setLoading] = useState(false);
  const [marketplaces, setMarketplaces] = useState([]);
  const [stores, setStores] = useState([]);
  const [summary, setSummary] = useState(null);
  const [vendorRows, setVendorRows] = useState([]);

  const [filters, setFilters] = useState({ marketplace: "", store: "" });

  const params = useMemo(() => {
    const p = {};
    if (filters.marketplace) p.marketplace_id = filters.marketplace;
    if (filters.store) p.store_id = filters.store;
    return p;
  }, [filters]);

  const fetchAll = async () => {
    try {
      setLoading(true);
      const [mp, storesData, summaryData, vendorsData] = await Promise.all([
        marketplaces.length ? Promise.resolve(marketplaces) : marketplaceAPI.getMarketplaces(),
        dashboardAPI.getStores(params),
        dashboardAPI.getSummary(params),
        dashboardAPI.getVendors(params),
      ]);
      if (!marketplaces.length) setMarketplaces(mp || []);
      setStores(storesData || []);
      setSummary(summaryData || null);
      setVendorRows(vendorsData || []);
    } catch (e) {
      console.error("Failed to load dashboard", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAll(); /* eslint-disable-next-line */ }, [filters.marketplace, filters.store]);

  const marketplaceOptions = marketplaces.map(m => ({ id: m.id, name: m.name }));
  const filteredStoreOptions = stores
    .filter(() => true)
    .map(s => ({ id: s.storeId, name: `${s.storeName} (${s.marketplace.name})` }));

  return (
    <div className="p-6 bg-walmart-gray min-h-screen space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <Button onClick={fetchAll} disabled={loading} className="walmart-button-primary">
          <RefreshCw className="mr-2 h-4 w-4" /> Refresh
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-col md:flex-row gap-4">
        <div className="w-full md:w-64">
          <label className="text-sm text-muted-foreground mb-1 block">Marketplace</label>
          <Select value={filters.marketplace || ALL_VALUE} onValueChange={(v) => setFilters(prev => ({ ...prev, marketplace: v === ALL_VALUE ? "" : v, store: "" }))}>
            <SelectTrigger className="w-full"><SelectValue placeholder="All" /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_VALUE}>All</SelectItem>
              {marketplaceOptions.map(m => (<SelectItem key={m.id} value={String(m.id)}>{m.name}</SelectItem>))}
            </SelectContent>
          </Select>
        </div>
        <div className="w-full md:w-72">
          <label className="text-sm text-muted-foreground mb-1 block">Store</label>
          <Select value={filters.store || ALL_VALUE} onValueChange={(v) => setFilters(prev => ({ ...prev, store: v === ALL_VALUE ? "" : v }))}>
            <SelectTrigger className="w-full"><SelectValue placeholder="All" /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_VALUE}>All</SelectItem>
              {filteredStoreOptions.map(s => (<SelectItem key={s.id} value={String(s.id)}>{s.name}</SelectItem>))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* KPI strip */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-6">
        <Kpi title="Total Products" value={summary?.totalProducts || 0} icon={<Package className="h-5 w-5" />} />
        <Kpi title="Active Stores" value={summary?.activeStores || 0} icon={<StoreIcon className="h-5 w-5" />} />
        <Kpi title="Vendors Covered" value={summary?.vendorsCovered || 0} icon={<Users className="h-5 w-5" />} />
        <Kpi title="Needs Rescrape" value={summary?.itemsNeedingRescrape || 0} icon={<AlertTriangle className="h-5 w-5" />} />
        <Kpi title="Errors (24h)" value={summary?.recentErrors24h || 0} icon={<AlertTriangle className="h-5 w-5" />} />
        <Kpi title="Uploads Today" value={summary?.uploadsToday || 0} icon={<Upload className="h-5 w-5" />} />
      </div>

      {/* Stores grid */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {stores.map(s => (
          <Card key={s.storeId} className="walmart-card">
            <CardHeader className="walmart-gradient text-white rounded-t-lg">
              <CardTitle className="flex items-center justify-between">
                <span>{s.storeName}</span>
                <span className="text-xs bg-white/20 rounded px-2 py-0.5">{s.marketplace.code}</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4 space-y-3">
              <div className="flex items-center justify-between"><span className="text-sm text-gray-600">Products</span><span className="font-semibold">{s.products}</span></div>
              <div className="flex items-center justify-between"><span className="text-sm text-gray-600">Vendors</span><span className="font-semibold">{s.vendors}</span></div>
              <div className="flex items-center justify-between"><span className="text-sm text-gray-600">Last scrape</span><span className="font-semibold">{s.lastScrapeAt ? new Date(s.lastScrapeAt).toLocaleString() : '—'}</span></div>
              <div className="flex items-center justify-between text-sm"><span className="text-gray-600">Scraping</span><span className={s.scrapingEnabled ? 'text-green-600' : 'text-gray-500'}>{s.scrapingEnabled ? 'Enabled' : 'Disabled'}</span></div>
              <div className="flex items-center justify-between text-sm"><span className="text-gray-600">Price updates</span><span className={s.priceUpdateEnabled ? 'text-green-600' : 'text-gray-500'}>{s.priceUpdateEnabled ? 'Enabled' : 'Disabled'}</span></div>
              {String(s.marketplace.code || '').toLowerCase() === 'mydeal' && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm"><span className="text-gray-600">MyDeal templates</span><span className={s.myDealTemplatesOk ? 'text-green-600' : 'text-red-600'}>{s.myDealTemplatesOk ? 'OK' : 'Missing'}</span></div>
                  <div className="flex items-center justify-between text-sm"><span className="text-gray-600">Last Price Export</span><span className="font-semibold">{s.lastExportPriceAt ? new Date(s.lastExportPriceAt).toLocaleString() : '—'}</span></div>
                  <div className="flex items-center justify-between text-sm"><span className="text-gray-600">Last Inventory Export</span><span className="font-semibold">{s.lastExportInventoryAt ? new Date(s.lastExportInventoryAt).toLocaleString() : '—'}</span></div>
                  <div className="flex gap-2">
                    <Button variant="secondary" size="sm" disabled={!s.lastExportPriceAt} onClick={() => window.open(exportAPI.downloadLatestUrl(s.storeId, 'price'), '_blank')}>
                      <Download className="w-4 h-4 mr-1" /> Price CSV
                    </Button>
                    <Button variant="secondary" size="sm" disabled={!s.lastExportInventoryAt} onClick={() => window.open(exportAPI.downloadLatestUrl(s.storeId, 'inventory'), '_blank')}>
                      <Download className="w-4 h-4 mr-1" /> Inventory CSV
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Vendors table */}
      <Card className="walmart-card">
        <CardHeader>
          <CardTitle>Vendors</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Vendor</TableHead>
                  <TableHead className="text-right">Products</TableHead>
                  <TableHead className="text-right">Out of Stock</TableHead>
                  <TableHead className="text-right">Avg Price</TableHead>
                  <TableHead className="text-right">Updated (24h)</TableHead>
                  <TableHead className="text-right">Errors (24h)</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {vendorRows.map(v => (
                  <TableRow key={v.vendorId}>
                    <TableCell>{v.vendorName}</TableCell>
                    <TableCell className="text-right">{v.products}</TableCell>
                    <TableCell className="text-right">{v.outOfStock}</TableCell>
                    <TableCell className="text-right">{Number(v.avgFinalPrice || 0).toFixed(2)}</TableCell>
                    <TableCell className="text-right">{v.priceUpdated24h}</TableCell>
                    <TableCell className="text-right">{v.recentErrors24h}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function Kpi({ title, value, icon }){
  return (
    <Card className="walmart-card">
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm text-gray-600">{title}</div>
            <div className="text-2xl font-bold">{value}</div>
          </div>
          <div className="bg-primary/10 p-3 rounded-full">{icon}</div>
        </div>
      </CardContent>
    </Card>
  );
}

