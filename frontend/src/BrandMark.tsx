type BrandMarkProps = {
  className?: string;
};

export function BrandMark({ className = "" }: BrandMarkProps) {
  return (
    <span className={`brand-mark ${className}`.trim()}>
      <img
        src="/brand/tx-comu-logo.png"
        alt="Texas Communications Unit (TX-COMU) logo"
        width="1563"
        height="1563"
      />
    </span>
  );
}
