interface WarningBannerProps {
  message: string;
}

export function WarningBanner({ message }: WarningBannerProps) {
  return <div className="pill pill-warning">{message}</div>;
}
