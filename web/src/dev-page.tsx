import { ArrowLeft, ArrowUpRight, CheckCircle2, Database, ExternalLink, FileDown, GitBranch, MonitorDown, Terminal } from "lucide-react"

const REPOSITORY_URL = "https://github.com/Hol-ick/tcg-trade-radar"
const RUNNER_URL = `${REPOSITORY_URL}/blob/main/debug/run-kaitori.bat`
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
          <div><strong>현재 휴대형 Collector.exe는 배포되어 있지 않습니다.</strong><p>저장소의 실행 가능한 수집 경로는 <code>debug\run-kaitori.bat</code>로 시작하는 PySide6 데스크톱 앱입니다. 가상환경의 <code>kaitori-collector.exe</code>는 콘솔 진입점 shim이라 휴대용 앱으로 안내하지 않습니다.</p></div>
        </section>

        <div className="collector-status-grid">
          <article className="collector-status-card">
            <span className="collector-card-icon violet"><MonitorDown size={18} /></span>
            <div><span className="eyebrow">로컬 앱</span><h2>데스크톱 수집기</h2><p>게임·기간·게시글 수를 설정하고 원문, 댓글, 정규화된 관측행을 로컬 SQLite에 저장합니다.</p><a className="inline-link" href={RUNNER_URL} target="_blank" rel="noreferrer">실행 파일 보기 <ExternalLink size={13} /></a></div>
          </article>
          <article className="collector-status-card">
            <span className="collector-card-icon green"><CheckCircle2 size={18} /></span>
            <div><span className="eyebrow">공개 데이터</span><h2>GitHub CSV 카탈로그</h2><p>게임·월·판매/구매/교환별 파일을 선택하면 해당 CSV만 브라우저로 가져옵니다.</p><a className="inline-link" href={CATALOG_URL} target="_blank" rel="noreferrer">카탈로그 열기 <ExternalLink size={13} /></a></div>
          </article>
        </div>

        <section className="collector-flow-card">
          <div className="section-heading"><div><span className="eyebrow">작업 흐름</span><h2>수집에서 분석까지</h2></div><span className="section-meta">한 번 수집하고, 필요한 파일만 조회</span></div>
          <div className="collector-steps">
            <CollectorStep number="01" icon={<MonitorDown size={17} />} title="데스크톱 앱 실행" description="프로젝트 폴더에서 실행 배치 파일을 열고 PySide6 앱을 시작합니다." code="debug\\run-kaitori.bat" />
            <CollectorStep number="02" icon={<Terminal size={17} />} title="수집·내보내기" description="게임과 기간을 설정해 수집하고, 앱에서 CSV를 내보냅니다. 원본과 검토행은 로컬 DB에 남습니다." />
            <CollectorStep number="03" icon={<GitBranch size={17} />} title="CSV를 Git에 반영" description="전처리·분할 스크립트로 GitHub Pages의 공개 데이터 카탈로그를 갱신합니다." code="scripts\\export_partitioned_market.py" />
            <CollectorStep number="04" icon={<FileDown size={17} />} title="탐색기에서 선택" description="시장 탐색기의 데이터 원본 선택기에서 공개 CSV 파일을 골라 가격·수요·공급을 분석합니다." />
          </div>
        </section>

        <section className="collector-help-grid">
          <article className="collector-help-card"><span className="eyebrow">빠른 시작</span><h2>Windows에서 시작</h2><pre><code>cd D:\\Files\\TASKS\\PROJECTS\\tcg_trade_radar
debug\\run-kaitori.bat</code></pre><p>처음 실행하는 PC라면 먼저 <code>python -m pip install -e .</code>을 실행하고 Playwright 브라우저 의존성을 준비하세요.</p><a className="button button-secondary" href={DESKTOP_DOC_URL} target="_blank" rel="noreferrer">데스크톱 앱 문서 <ExternalLink size={14} /></a></article>
          <article className="collector-help-card"><span className="eyebrow">데이터 약속</span><h2>페이지가 읽는 데이터</h2><ul><li><strong>관측행 CSV</strong><span>카드명·판매자·거래유형·가격·수량·게시시각</span></li><li><strong>파일 인덱스</strong><span>게임·월·거래유형·행 수·기간</span></li><li><strong>중복 방지</strong><span>관측 ID를 기준으로 한 행만 유지</span></li></ul><a className="button button-secondary" href={CATALOG_URL} target="_blank" rel="noreferrer">공개 데이터 보기 <ExternalLink size={14} /></a></article>
        </section>
      </div>
    </section>
  </main>
}

function CollectorStep({ number, icon, title, description, code }: { number: string; icon: React.ReactNode; title: string; description: string; code?: string }) {
  return <article className="collector-step"><div className="collector-step-top"><span className="collector-step-number">{number}</span><span className="collector-step-icon">{icon}</span></div><h3>{title}</h3><p>{description}</p>{code && <code className="collector-step-code">{code}</code>}</article>
}
