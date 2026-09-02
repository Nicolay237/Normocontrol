import { Uploader } from './Uploader.tsx'
import type { CheckStatus } from '../hooks/useDocumentCheck.ts'
import './Hero.css'

interface HeroProps {
  readonly file: File | null
  readonly status: CheckStatus
  readonly errorMessage: string | null
  readonly onSelectFile: (file: File | null) => void
  readonly onSubmit: () => void
}

export function Hero(props: HeroProps) {
  return (
    <header className="nc-hero">
      <div className="nc-hero__text">
        <h1>Проверьте оформление работы раньше, чем это сделает нормоконтролёр</h1>
        <p className="nc-hero__sub">
          Загрузите .docx или .pdf — сервис разберёт поля, шрифт, интервалы, отступы и заголовки и покажет отклонения с
          указанием страницы и абзаца.
        </p>
        <p className="nc-hero__sub nc-hero__upload-note">
          <strong>Загружайте только текст самой работы</strong> — от «Введения» до приложений. Без титульного листа,
          задания на ВКР, отзыва, рецензии, аннотации на отдельном листе и других сопроводительных документов: они не
          входят в нормоконтроль и могут исказить результат проверки.
        </p>

        <Uploader {...props} />
      </div>

      <div className="nc-hero__stamp" aria-hidden="true">
        <div className="nc-stamp-ring">
          <span>ГОСТ 7.32-2017</span>
        </div>
      </div>
    </header>
  )
}
