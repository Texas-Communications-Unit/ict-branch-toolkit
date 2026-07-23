type BrandMarkProps = {
  className?: string;
};

export function BrandMark({ className = "" }: BrandMarkProps) {
  return (
    <picture className={`brand-mark ${className}`.trim()}>
      <source
        srcSet="/brand/tx-comu-logo-transparent.svg"
        type="image/svg+xml"
      />
      <img
        src="/brand/tx-comu-logo.png"
        alt="Texas Communications Unit (TX-COMU) logo"
        width="1563"
        height="1563"
      />
    </picture>
  );
}
