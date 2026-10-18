import { Component } from 'react'

// Evita la pantalla en blanco si una pantalla falla al dibujarse: muestra un mensaje y un
// boton para recargar la pagina.
export default class ErrorBoundary extends Component {
  state = { fallo: false }

  static getDerivedStateFromError() {
    return { fallo: true }
  }

  componentDidCatch(error, info) {
    console.error('Error al mostrar la pantalla', error, info?.componentStack)
  }

  render() {
    if (!this.state.fallo) return this.props.children
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
        <div role="alert" className="max-w-md w-full bg-white rounded-lg border border-slate-200 shadow-sm p-6 text-center space-y-3">
          <h1 className="text-xl font-bold text-slate-900">Algo salió mal</h1>
          <p className="text-sm text-slate-600">
            Ocurrió un error inesperado al mostrar esta pantalla. Recarga la página para volver a intentarlo.
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700"
          >
            Recargar
          </button>
        </div>
      </div>
    )
  }
}
