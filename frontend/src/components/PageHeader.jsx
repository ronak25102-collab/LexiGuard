import SplitHeading from './SplitHeading';
import Reveal from './Reveal';

// Header for inner pages, laid out like the reference site's sub-page heroes:
// generous top space, an index line, a line-revealed heading, and a rule.
export default function PageHeader({ index, eyebrow, title, description, actions, children }) {
  return (
    <header className="page-header container-x">
      <div className="page-header__grid">
        <div>
          <Reveal self className="page-header__top">
            <span className="bolt" aria-hidden="true" />
            <span>{index ? `${index} / ` : ''}{eyebrow}</span>
          </Reveal>
          <SplitHeading as="h1" trigger="mount" delay={0.1} className="page-header__title display-xl">
            {title}
          </SplitHeading>
          {description && (
            <SplitHeading as="p" trigger="mount" delay={0.35} className="page-header__desc">
              {description}
            </SplitHeading>
          )}
        </div>
        {actions && <Reveal className="flex flex-wrap gap-3" delay={0.5}>{actions}</Reveal>}
      </div>
      {children}
      <div className="hairline page-header__rule" />
    </header>
  );
}
