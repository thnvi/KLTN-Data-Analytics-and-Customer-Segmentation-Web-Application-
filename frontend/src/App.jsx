import { Fragment, useEffect, useMemo, useState } from 'react'
import axios from 'axios'
import {
  Activity,
  BarChart3,
  Database,
  Film,
  Filter,
  Globe2,
  RefreshCw,
  Search,
  Sparkles,
  TrendingUp,
} from 'lucide-react'
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
} from 'recharts'

const YEARS = [2020, 2021, 2022, 2023, 2024, 2025]
const MONTHS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

const emptyHeatmap = YEARS.flatMap((year) => MONTHS.map((month) => ({ month, year, value: 0 })))

const fallbackData = {
  monthly: [],
  genres: [],
  ratings: [],
  topTitles: [],
  countries: [],
  heatmap: emptyHeatmap,
  insights: [
    { title: 'Backend chưa kết nối', text: 'Hãy chạy FastAPI ở cổng 8000 để dashboard lấy dữ liệu thật.' },
  ],
  dataQuality: { analysis_period: '2020-2025', heatmap_cells: 72, heatmap_total: 0 },
  kpis: {
    total_titles: '0',
    genre_count: '0',
    forecast_horizon: '6 months',
    models_ready: '3',
    top10_latest_week: 'N/A',
    engagement_rows: '0',
  },
  filterOptions: {
    genres: [],
    years: YEARS.map(String),
    months: MONTHS.map((m) => ({ value: String(m).padStart(2, '0'), label: `Tháng ${m}` })),
    countries: [],
  },
}

const piePalette = ['#991b1b', '#dc2626', '#2563eb', '#0f766e', '#f59e0b', '#64748b']
const monthLabels = [
  { value: 'all', label: 'Tất cả tháng' },
  ...MONTHS.map((m) => ({ value: String(m).padStart(2, '0'), label: `Tháng ${m}` })),
]

function StatCard({ title, value, hint, Icon }) {
  return (
    <div className="card stat-card">
      <div>
        <div className="muted label">{title}</div>
        <div className="stat-value">{value}</div>
        <div className="muted">{hint}</div>
      </div>
      <div className="icon-box"><Icon size={20} /></div>
    </div>
  )
}

function normalizeHeatmap(data) {
  const map = new Map()
  ;(Array.isArray(data) ? data : []).forEach((item) => {
    const month = Number(item.month)
    const year = Number(item.year)
    const value = Number(item.value) || 0
    if (MONTHS.includes(month) && YEARS.includes(year)) {
      map.set(`${month}-${year}`, value)
    }
  })
  return YEARS.flatMap((year) => MONTHS.map((month) => ({
    month,
    year,
    value: map.get(`${month}-${year}`) ?? 0,
  })))
}

function HeatmapGrid({ data }) {
  const cells = normalizeHeatmap(data)
  const maxValue = Math.max(...cells.map((d) => d.value), 1)
  const total = cells.reduce((sum, item) => sum + item.value, 0)

  return (
    <div className="heatmap-wrap">
      <div className="heatmap-toolbar">
        <div>
          <strong>{total.toLocaleString('vi-VN')}</strong> nội dung trong heatmap
        </div>
        <div className="muted small">Luôn hiển thị đủ 12 tháng × 6 năm</div>
      </div>

      <div className="heatmap-grid" style={{ gridTemplateColumns: `96px repeat(${YEARS.length}, minmax(72px, 1fr))` }}>
        <div className="heatmap-head">Tháng/Năm</div>
        {YEARS.map((year) => <div key={year} className="heatmap-head">{year}</div>)}

        {MONTHS.map((month) => (
          <Fragment key={month}>
            <div className="heatmap-month">Tháng {month}</div>
            {YEARS.map((year) => {
              const item = cells.find((d) => d.month === month && d.year === year)
              const value = item?.value ?? 0
              const intensity = value / maxValue
              const opacity = value === 0 ? 0.06 : 0.18 + intensity * 0.76
              return (
                <div
                  key={`${month}-${year}`}
                  className={value === 0 ? 'heatmap-cell zero' : 'heatmap-cell'}
                  title={`Tháng ${month}/${year}: ${value} nội dung`}
                  style={{ backgroundColor: `rgba(153, 27, 27, ${opacity})` }}
                >
                  {value}
                </div>
              )
            })}
          </Fragment>
        ))}
      </div>
    </div>
  )
}

function EmptyChart({ text }) {
  return <div className="empty-state">{text}</div>
}

export default function App() {
  const [model, setModel] = useState('random_forest')
  const [loading, setLoading] = useState(false)
  const [apiError, setApiError] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [selectedGenre, setSelectedGenre] = useState('all')
  const [selectedYear, setSelectedYear] = useState('all')
  const [selectedMonth, setSelectedMonth] = useState('all')
  const [selectedCountry, setSelectedCountry] = useState('all')
  const [data, setData] = useState(fallbackData)

  useEffect(() => {
    const loadDashboard = async () => {
      setLoading(true)
      try {
        const response = await axios.get('/api/dashboard', {
          params: {
            model,
            genre: selectedGenre,
            year: selectedYear,
            month: selectedMonth,
            country: selectedCountry,
          },
        })

        const nextData = {
          ...fallbackData,
          ...response.data,
          heatmap: normalizeHeatmap(response.data?.heatmap),
          insights: Array.isArray(response.data?.insights) && response.data.insights.length
            ? response.data.insights
            : fallbackData.insights,
        }
        setData(nextData)
        setApiError(false)
      } catch (error) {
        console.error('Dashboard load error:', error)
        setApiError(true)
        // Giữ lại dữ liệu đang hiển thị thay vì xoá trắng dashboard.
        // Nhờ vậy khi đổi tab Prophet/ARIMA mà backend chậm hoặc lỗi tạm thời,
        // biểu đồ không bị mất tiêu.
        setData((prev) => prev?.monthly?.length ? prev : fallbackData)
      } finally {
        setLoading(false)
      }
    }
    loadDashboard()
  }, [model, selectedGenre, selectedYear, selectedMonth, selectedCountry])

  const filterOptions = useMemo(() => ({
    genres: ['all', ...(data.filterOptions?.genres ?? [])],
    years: ['all', ...(data.filterOptions?.years ?? YEARS.map(String))],
    months: data.filterOptions?.months?.length
      ? [{ value: 'all', label: 'Tất cả tháng' }, ...data.filterOptions.months]
      : monthLabels,
    countries: ['all', ...(data.filterOptions?.countries ?? data.countries?.map((item) => item.country) ?? [])],
  }), [data.filterOptions, data.countries])

  const filteredTopTitles = useMemo(() => {
    const topTitles = Array.isArray(data.topTitles) ? data.topTitles : []
    if (!keyword.trim()) return topTitles
    return topTitles.filter((item) => String(item.title).toLowerCase().includes(keyword.toLowerCase()))
  }, [data.topTitles, keyword])

  const filterSummary = useMemo(() => {
    const genreLabel = selectedGenre === 'all' ? 'Tất cả thể loại' : selectedGenre
    const yearLabel = selectedYear === 'all' ? 'Tất cả năm' : `Năm ${selectedYear}`
    const monthLabel = monthLabels.find((item) => item.value === selectedMonth)?.label ?? 'Tất cả tháng'
    const countryLabel = selectedCountry === 'all' ? 'Tất cả quốc gia' : selectedCountry
    return `${genreLabel} • ${yearLabel} • ${monthLabel} • ${countryLabel}`
  }, [selectedGenre, selectedYear, selectedMonth, selectedCountry])

  const resetFilters = () => {
    setSelectedGenre('all')
    setSelectedYear('all')
    setSelectedMonth('all')
    setSelectedCountry('all')
  }

  return (
    <div className="page">
      <div className="container">
        <header className="hero">
          <div className="hero-left">
            <div className="logo-box">N</div>
            <div>
              <h1>Netflix Trend Analytics Dashboard</h1>
              <p>Dashboard phân tích xu hướng nội dung Netflix giai đoạn 2020–2025, kết hợp catalog, Top 10 Weekly và Engagement Report.</p>
            </div>
          </div>
          <div className="hero-actions">
            <div className="search-box">
              <Search size={18} />
              <input value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder="Tìm trong top nội dung..." />
            </div>
            <button className="primary-btn" onClick={() => window.location.reload()}><RefreshCw size={16} /> Refresh</button>
          </div>
        </header>

        {apiError && (
          <div className="alert-box">
            Không kết nối được backend ở cổng 8000. Hãy chạy backend trước rồi bấm Ctrl + F5.
          </div>
        )}

        <section className="filter-panel card">
          <div className="filter-header">
            <div className="filter-title">
              <Filter size={20} />
              <div>
                <h2>Bộ lọc dữ liệu</h2>
                <div className="muted small">Dashboard chỉ dùng giai đoạn 2020–2025.</div>
              </div>
            </div>
            <button className="secondary-btn" onClick={resetFilters}>Xóa bộ lọc</button>
          </div>
          <div className="filter-grid">
            <div className="filter-item">
              <label>Thể loại</label>
              <select value={selectedGenre} onChange={(e) => setSelectedGenre(e.target.value)}>
                {filterOptions.genres.map((item) => <option key={item} value={item}>{item === 'all' ? 'Tất cả thể loại' : item}</option>)}
              </select>
            </div>
            <div className="filter-item">
              <label>Năm</label>
              <select value={selectedYear} onChange={(e) => setSelectedYear(e.target.value)}>
                {filterOptions.years.map((item) => <option key={item} value={item}>{item === 'all' ? 'Tất cả năm' : item}</option>)}
              </select>
            </div>
            <div className="filter-item">
              <label>Tháng</label>
              <select value={selectedMonth} onChange={(e) => setSelectedMonth(e.target.value)}>
                {filterOptions.months.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
            </div>
            <div className="filter-item">
              <label>Quốc gia</label>
              <select value={selectedCountry} onChange={(e) => setSelectedCountry(e.target.value)}>
                {filterOptions.countries.map((item) => <option key={item} value={item}>{item === 'all' ? 'Tất cả quốc gia' : item}</option>)}
              </select>
            </div>
            <div className="filter-item">
              <label>Đang xem</label>
              <div className="filter-summary">{filterSummary}</div>
            </div>
          </div>
        </section>

        <section className="stats-grid">
          <StatCard title="Tổng số nội dung" value={data.kpis.total_titles} hint="Sau khi lọc 2020–2025" Icon={Film} />
          <StatCard title="Số lượng thể loại" value={data.kpis.genre_count} hint="Tách từ listed_in" Icon={BarChart3} />
          <StatCard title="Top 10 mới nhất" value={data.kpis.top10_latest_week || 'N/A'} hint="Theo dữ liệu weekly" Icon={Database} />
          <StatCard title="Mô hình" value={data.kpis.models_ready} hint="Prophet, ARIMA, RF" Icon={Activity} />
        </section>

        <section className="insight-grid">
          {(data.insights ?? []).map((item, index) => (
            <div className="card insight-card" key={`${item.title}-${index}`}>
              <div className="insight-icon"><Sparkles size={18} /></div>
              <div>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
              </div>
            </div>
          ))}
        </section>

        <section className="main-grid">
          <div className="left-column">
            <div className="card large-card">
              <div className="card-header">
                <div>
                  <h2>Xu hướng nội dung theo tháng</h2>
                  <p className="muted">Actual lấy từ date_added; forecast dùng mô hình đang chọn.</p>
                </div>
                <div className="tab-row">
                  <button className={model === 'prophet' ? 'tab active' : 'tab'} onClick={() => setModel('prophet')}>Prophet</button>
                  <button className={model === 'random_forest' ? 'tab active' : 'tab'} onClick={() => setModel('random_forest')}>Random Forest</button>
                  <button className={model === 'arima' ? 'tab active' : 'tab'} onClick={() => setModel('arima')}>ARIMA</button>
                </div>
              </div>
              <div className="chart-box tall">
                {data.monthly?.length ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={data.monthly}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="month" minTickGap={24} />
                      <YAxis />
                      <Tooltip />
                      <Line name="Actual" type="monotone" dataKey="actual" stroke="#991b1b" strokeWidth={3} dot={false} connectNulls={false} />
                      <Line name="Forecast" type="monotone" dataKey="forecast" stroke="#1d4ed8" strokeWidth={3} strokeDasharray="6 6" dot={false} connectNulls={false} />
                    </LineChart>
                  </ResponsiveContainer>
                ) : <EmptyChart text="Chưa có dữ liệu xu hướng. Kiểm tra backend hoặc bộ lọc." />}
              </div>
            </div>

            <div className="card large-card hero-chart-card">
              <div className="card-header">
                <div>
                  <h2>Heatmap: Nội dung theo tháng và năm</h2>
                  <p className="muted">Nằm ngay dưới biểu đồ xu hướng. Hiển thị đủ 72 ô cho 12 tháng × 6 năm để thấy tháng/năm nào có nhiều nội dung nhất.</p>
                </div>
                <div className="badge">2020–2025</div>
              </div>
              <div className="chart-box heatmap-box">
                <HeatmapGrid data={data.heatmap} />
              </div>
            </div>

            <div className="sub-grid">
              <div className="card">
                <div className="card-header"><h2>Top thể loại</h2></div>
                <div className="chart-box medium">
                  {data.genres?.length ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={data.genres} layout="vertical" margin={{ left: 10, right: 10 }}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis type="number" />
                        <YAxis type="category" dataKey="name" width={120} />
                        <Tooltip />
                        <Bar dataKey="value" fill="#991b1b" radius={[0, 10, 10, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : <EmptyChart text="Không có dữ liệu thể loại." />}
                </div>
              </div>

              <div className="card">
                <div className="card-header"><h2>Phân bố rating</h2></div>
                <div className="chart-box medium">
                  {data.ratings?.length ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie data={data.ratings} dataKey="value" nameKey="name" outerRadius={100} label>
                          {data.ratings.map((entry, index) => (
                            <Cell key={entry.name} fill={piePalette[index % piePalette.length]} />
                          ))}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  ) : <EmptyChart text="Không có dữ liệu rating." />}
                </div>
              </div>
            </div>
          </div>

          <div className="right-column">
            <div className="card">
              <div className="card-header">
                <div>
                  <h2>Top nội dung nổi bật</h2>
                  <div className="muted small">Xếp theo engagement score và popularity.</div>
                </div>
                <div className="badge">Live</div>
              </div>
              <div className="list-box">
                {filteredTopTitles.length ? filteredTopTitles.map((item) => (
                  <div className="rank-item" key={`${item.rank}-${item.title}`}>
                    <div className="rank-left">
                      <div className="rank-number">{item.rank}</div>
                      <div>
                        <div className="rank-title">{item.title}</div>
                        <div className="muted small">Nguồn: {item.model}</div>
                      </div>
                    </div>
                    <div className="score-pill">{item.score}</div>
                  </div>
                )) : <EmptyChart text="Không tìm thấy nội dung phù hợp." />}
              </div>
            </div>

            <div className="card">
              <div className="card-header"><h2><Globe2 size={18} /> Phân bố quốc gia</h2></div>
              <div className="country-list">
                {(data.countries ?? []).length ? data.countries.map((item) => (
                  <div className="country-item" key={item.country}>
                    <span>{item.country}</span>
                    <strong>{item.count}</strong>
                  </div>
                )) : <EmptyChart text="Không có dữ liệu quốc gia." />}
              </div>
            </div>
          </div>
        </section>

        <div className="status-box">
          {loading
            ? 'Đang tải dữ liệu dashboard...'
            : apiError
              ? 'Không kết nối được backend. Hãy chạy backend ở cổng 8000.'
              : `Dashboard đã sẵn sàng. Heatmap: ${data.dataQuality?.heatmap_cells ?? 72} ô, tổng ${Number(data.dataQuality?.heatmap_total ?? 0).toLocaleString('vi-VN')} nội dung.`}
        </div>
      </div>
    </div>
  )
}
