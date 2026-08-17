import { ArrowLeft, ArrowUpRight, CheckCircle2, Database, ExternalLink, FileDown, GitBranch, MonitorDown, Terminal } from "lucide-react"

const REPOSITORY_URL = "https://github.com/Hol-ick/tcg-trade-radar"
const RUNNER_URL = `${REPOSITORY_URL}/blob/main/TCG%20Trade%20Radar.bat`
const DESKTOP_DOC_URL = `${REPOSITORY_URL}/blob/main/docs/desktop-app.md`
const CATALOG_URL = `${REPOSITORY_URL}/tree/main/web/public/data/analysis/market-20260814`

export function DevPage() {
  return <CollectorGuide />
}

export function CollectorGuide() {
  return <main className="explorer-shell explorer-dense collector-shell">
    <aside className="saas-sidebar">
      <a className="saas-brand" href={import.meta.env.BASE_URL} aria-label="Trade Radar 홈">
        <span className="brand-mark">TR</span>
        <span><strong>Trade Radar</strong><small>거래 시장 분석</small></span>
      </a>

      <div className="sidebar-section-label">작업공간</div>
      <nav className="sidebar-nav" aria-label="주 메뉴">
        <a href={import.meta.env.BASE_URL}><Database size={16} />시장 개요</a>
        <a href={`${import.meta.env.BASE_URL}#signals`}><Database size={16} />카드 신호</a>
        <a className="active" href="?page=collector"><MonitorDown size={16} />수집기</a>
      </nav>

      <div className="sidebar-divider" />
      <div className="sidebar-section-label">데이터 원본</div>
      <div className="sidebar-source">
        <span className="source-icon"><GitBranch size={15} /></span>
        <span><strong>공개 CSV 카탈로그</strong><small>54개 분석 파일</small></span>
      </div>
      <div className="sidebar-spacer" />
      <div className="sidebar-workspace"><span>TCG</span><span><strong>개인 작업공간</strong><small>CSV 시장 분석</small></span></div>
    </aside>

    <section className="saas-main">
      <header className="saas-header">
        <div className="breadcrumbs"><span>작업공간</span><span>/</span><strong>수집기</strong></div>
        <div className="header-actions"><span className="connection-pill"><i />데스크톱 앱 안내</span><a className="header-collector-link" href={import.meta.env.BASE_URL}>시장 탐색기로 돌아가기 <ArrowUpRight size={14} /></a></div>
      </header>

      <div className="saas-content collector-content">
        <section className="page-heading collector-heading">
          <div><span className="eyebrow">수집기</span><h1>수집은 데스크톱 앱에서 실행합니다.</h1><p>GitHub Pages는 브라우저 보안상 사용자의 PC에서 EXE를 직접 실행할 수 없습니다. 로컬 수집기를 실행한 뒤 결과 CSV를 Git에 올리면, 이 페이지가 최신 카탈로그를 읽어 분석합니다.</p></div>
          <a className="button button-primary" href={import.meta.env.BASE_URL}><ArrowLeft size={16} />시장 탐색기</a>
        </section>

        <section className="collector-alert" role="note">
          <span className="collector-alert-icon"><Terminal size={18} /></span>
          <div><strong>실제 수집은 로컬 앱에서 실행합니다.</strong><p>저장소 루트의 <code>TCG Trade Radar.bat</code> 하나만 실행하면 됩니다. 첫 실행일 때만 환경 준비와 점검을 진행하고, 이후에는 PySide6 데스크톱 앱을 바로 엽니다.</p></div>
        </section>

        <div className="collector-status-grid">
          <article className="collector-status-card">
            <span className="collector-card-icon violet"><MonitorDown size={18} /></span>
            <div><span className="eyebrow">로컬 앱</span><h2>데스크톱 수집기</h2><p>게임·기간·게시글 수를 설정하고 원문, 댓글, 정규화된 관측행을 로컬 SQLite에 저장합니다.</p><a className="inline-link" href={RUNNER_URL} target="_blank" rel="noreferrer">실행 배치 보기 <ExternalLink size={13} /></a></div>
          </article>
          <article className="collector-status-card">
            <span className="collector-card-icon green"><CheckCircle2 size={18} /></span>
            <div><span className="eyebrow">공개 데이터</span><h2>GitHub CSV 카탈로그</h2><p>게임·월·판매/구매/교환별 파일을 선택하면 해당 CSV만 브라우저로 가져옵니다.</p><a className="inline-link" href={CATALOG_URL} target="_blank" rel="noreferrer">카탈로그 열기 <ExternalLink size={13} /></a></div>
          </article>
        </div>

        <section className="collector-flow-card">
          <div className="section-heading"><div><span className="eyebrow">작업 흐름</span><h2>수집에서 분석까지</h2></div><span className="section-meta">한 번 수집하고, 필요한 파일만 조회</span></div>
          <div className="collector-steps">
            <CollectorStep number="01" icon={<MonitorDown size={17} />} title="첫 실행 준비" description="루트 실행기가 저장소 위치를 자동으로 찾아 .venv와 PySide6·Playwright를 준비하고 상태를 점검합니다." code="TCG Trade Radar.bat" />
            <CollectorStep number="02" icon={<Terminal size={17} />} title="수집 실행" description="앱에서 게임·기간·글 수를 설정해 수집합니다. 다음 실행부터는 이 단계로 바로 들어갑니다." code="TCG Trade Radar.bat" />
            <CollectorStep number="03" icon={<GitBranch size={17} />} title="CSV 내보내기·반영" description="앱에서 CSV를 내보내고, 검토한 공개 데이터만 전처리·분할 스크립트로 GitHub Pages 카탈로그에 반영합니다." code="scripts\\export_partitioned_market.py" />
            <CollectorStep number="04" icon={<FileDown size={17} />} title="탐색기에서 선택" description="시장 탐색기의 데이터 원본 선택기에서 공개 CSV 파일을 골라 가격·수요·공급을 분석합니다." />
          </div>
        </section>

        <section className="collector-help-grid">
          <article className="collector-help-card"><span className="eyebrow">빠른 시작</span><h2>Windows에서 시작</h2><pre><code>TCG Trade Radar.bat</code></pre><p>첫 실행만 설치·점검을 수행하고, 이후에는 이 파일 하나로 앱을 엽니다.</p><a className="button button-secondary" href={DESKTOP_DOC_URL} target="_blank" rel="noreferrer">데스크톱 앱 문서 <ExternalLink size={14} /></a></article>
          <article className="collector-help-card"><span className="eyebrow">데이터 약속</span><h2>페이지가 읽는 데이터</h2><ul><li><strong>관측행 CSV</strong><span>카드명·판매자·거래유형·가격·수량·게시시각</span></li><li><strong>파일 인덱스</strong><span>게임·월·거래유형·행 수·기간</span></li><li><strong>중복 방지</strong><span>관측 ID를 기준으로 한 행만 유지</span></li></ul><a className="button button-secondary" href={CATALOG_URL} target="_blank" rel="noreferrer">공개 데이터 보기 <ExternalLink size={14} /></a></article>
        </section>
      </div>
    </section>
  </main>
}

function CollectorStep({ number, icon, title, description, code }: { number: string; icon: React.ReactNode; title: string; description: string; code?: string }) {
  return <article className="collector-step"><div className="collector-step-top"><span className="collector-step-number">{number}</span><span className="collector-step-icon">{icon}</span></div><h3>{title}</h3><p>{description}</p>{code && <code className="collector-step-code">{code}</code>}</article>
}
