import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Hola mundo",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
