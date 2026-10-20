import { useEffect, useState } from 'react'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const clp = (cents) => `$${(cents / 100).toLocaleString('es-CL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

export default function App() {
  const [products, setProducts] = useState([])
  const [cart, setCart] = useState({}) // product_id -> qty
  const [orderId, setOrderId] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch(`${API}/products`).then((r) => r.json()).then(setProducts).catch((e) => setError(String(e)))
  }, [])

  const add = (id) => setCart({ ...cart, [id]: (cart[id] || 0) + 1 })
  const total = products.reduce((sum, p) => sum + p.price_cents * (cart[p.id] || 0), 0)

  const buy = async () => {
    setError(null)
    const items = Object.entries(cart).map(([product_id, qty]) => ({ product_id: Number(product_id), qty }))
    const res = await fetch(`${API}/orders`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ items }),
    })
    const body = await res.json()
    if (!res.ok) return setError(body.detail || res.statusText)
    setOrderId(body.id)
    setCart({})
  }

  return (
    <main style={{ fontFamily: 'sans-serif', maxWidth: 520, margin: '2rem auto' }}>
      <h1>Mini shop</h1>
      <ul>
        {products.map((p) => (
          <li key={p.id}>
            {p.name} — {clp(p.price_cents)} (stock {p.stock}){' '}
            <button onClick={() => add(p.id)}>Agregar</button>
            {cart[p.id] ? ` ×${cart[p.id]}` : ''}
          </li>
        ))}
      </ul>
      <p>Total: <strong>{clp(total)}</strong></p>
      <button onClick={buy} disabled={total === 0}>Comprar</button>
      {orderId && <p>Pedido creado: #{orderId}</p>}
      {error && <p style={{ color: 'crimson' }}>{error}</p>}
    </main>
  )
}
