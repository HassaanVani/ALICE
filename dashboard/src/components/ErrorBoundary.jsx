import React from 'react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          gap: 12,
          padding: 24,
          background: 'var(--bg-panel)',
          border: '1px solid var(--border-color)',
          borderRadius: 6,
          fontFamily: 'var(--font-mono)',
        }}>
          <div style={{ color: 'var(--danger)', fontSize: 12, fontWeight: 600, textTransform: 'uppercase' }}>
            Panel Error
          </div>
          <div style={{ color: 'var(--text-dim)', fontSize: 10, textAlign: 'center', maxWidth: 260 }}>
            {this.state.error?.message || 'Something went wrong rendering this panel.'}
          </div>
          <button
            className="btn"
            onClick={() => this.setState({ hasError: false, error: null })}
            style={{ fontSize: 10, padding: '4px 14px' }}
          >
            Retry
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
