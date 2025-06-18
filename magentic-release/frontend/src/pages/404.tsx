import * as React from "react"
import { Link, HeadFC, PageProps } from "gatsby"

const containerStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  minHeight: "100vh",
  padding: "2rem",
  textAlign: "center",
  backgroundColor: "#f8f9fa",
  fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif"
}

const headingStyle: React.CSSProperties = {
  fontSize: "6rem",
  margin: 0,
  color: "#343a40",
  fontWeight: 700
}

const subheadingStyle: React.CSSProperties = {
  fontSize: "2rem",
  margin: "1rem 0 2rem",
  color: "#495057",
  fontWeight: 500
}

const textStyle: React.CSSProperties = {
  fontSize: "1.2rem",
  marginBottom: "2rem",
  color: "#6c757d",
  maxWidth: "600px"
}

const linkStyle: React.CSSProperties = {
  display: "inline-block",
  padding: "0.75rem 1.5rem",
  backgroundColor: "#007bff",
  color: "white",
  textDecoration: "none",
  borderRadius: "4px",
  fontWeight: 500,
  transition: "background-color 0.2s ease"
}

const NotFoundPage: React.FC<PageProps> = () => {
  return (
    <main style={containerStyle}>
      <h1 style={headingStyle}>404</h1>
      <h2 style={subheadingStyle}>Page Not Found</h2>
      <p style={textStyle}>
        Sorry, we couldn't find the page you're looking for. The page might have been moved, deleted, or never existed.
      </p>
      <Link to="/" style={linkStyle} onMouseOver={(e) => {
        e.currentTarget.style.backgroundColor = "#0069d9";
      }} onMouseOut={(e) => {
        e.currentTarget.style.backgroundColor = "#007bff";
      }}>
        Return to Home
      </Link>
    </main>
  )
}

export default NotFoundPage

export const Head: HeadFC = () => <title>Page Not Found | Magentic-UI </title>
