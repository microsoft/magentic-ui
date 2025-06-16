import * as React from "react";
import MagenticUILayout from "../components/layout";
import { graphql } from "gatsby";

// markup
const IndexPage = ({ data }: any) => {
  return (
    <MagenticUILayout meta={data.site.siteMetadata} title="Home" link={"/"}>
      <main style={{ height: "100%" }} className=" h-full ">
      </main>
    </MagenticUILayout>
  );
};

export const query = graphql`
  query HomePageQuery {
    site {
      siteMetadata {
        description
        title
      }
    }
  }
`;

export default IndexPage;
