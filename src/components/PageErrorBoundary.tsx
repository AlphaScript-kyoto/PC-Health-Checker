import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallbackTitle?: string
  onRetry?: () => void
}

interface State {
  error: Error | null
}

/** 1画面の例外でアプリ全体が真っ白にならないようにする */
export class PageErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('page render error', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="page">
          <div className="page-head">
            <h2>{this.props.fallbackTitle || '表示エラー'}</h2>
            <p>この画面の表示中に問題が起きました。</p>
          </div>
          <section className="panel">
            <p className="muted" style={{ marginTop: 0 }}>
              {this.state.error.message || String(this.state.error)}
            </p>
            <button
              type="button"
              className="btn primary"
              onClick={() => {
                this.setState({ error: null })
                this.props.onRetry?.()
              }}
            >
              もう一度表示する
            </button>
          </section>
        </div>
      )
    }
    return this.props.children
  }
}
