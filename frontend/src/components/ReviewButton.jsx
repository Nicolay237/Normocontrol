import { Link } from "react-router-dom";
import { Icon } from "../ui.jsx";

/** Переход к форме отзыва после проверки (from="check") или исправления (from="fix"). */
export default function ReviewButton({ from }) {
  return (
    <Link to={`/reviews?from=${from}`} className="link-btn">
      <md-text-button>
        <Icon name="review" slot="icon" />
        Оставить отзыв
      </md-text-button>
    </Link>
  );
}
