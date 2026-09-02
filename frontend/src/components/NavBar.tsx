import './NavBar.css'

export function NavBar() {
  return (
    <nav className="nc-nav">
      <div className="nc-nav__mark">
        <span className="nc-nav__seal" aria-hidden="true">
          ⬤
        </span>
        Нормоконтроль
      </div>
      <div className="nc-nav__std">ГОСТ 7.32&#8209;2017</div>
    </nav>
  )
}
