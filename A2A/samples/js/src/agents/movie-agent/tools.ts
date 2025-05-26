import { ai, z } from "./genkit.js";
import { callTmdbApi } from "./tmdb.js";

export const searchMovies = ai.defineTool(
  {
    name: "searchMovies",
    description: "search TMDB for movies by title",
    inputSchema: z.object({
      query: z.string(),
    }),
  },
  async ({ query }) => {
    console.log("[tmdb:searchMovies]", JSON.stringify(query));
    try {
      const data = await callTmdbApi("movie", query);

      // Only modify image paths to be full URLs
      const results = data.results.map((movie: any) => {
        if (movie.poster_path) {
          movie.poster_path = `https://image.tmdb.org/t/p/w500${movie.poster_path}`;
        }
        if (movie.backdrop_path) {
          movie.backdrop_path = `https://image.tmdb.org/t/p/w500${movie.backdrop_path}`;
        }
        return movie;
      });

      return {
        ...data,
        results,
      };
    } catch (error) {
      console.error("Error searching movies:", error);
      // Re-throwing allows Genkit/the caller to handle it appropriately
      throw error;
    }
  }
);

export const searchPeople = ai.defineTool(
  {
    name: "searchPeople",
    description: "search TMDB for people by name",
    inputSchema: z.object({
      query: z.string(),
    }),
  },
  async ({ query }) => {
    console.log("[tmdb:searchPeople]", JSON.stringify(query));
    try {
      const data = await callTmdbApi("person", query);

      // Only modify image paths to be full URLs
      const results = data.results.map((person: any) => {
        if (person.profile_path) {
          person.profile_path = `https://image.tmdb.org/t/p/w500${person.profile_path}`;
        }

        // Also modify poster paths in known_for works
        if (person.known_for && Array.isArray(person.known_for)) {
          person.known_for = person.known_for.map((work: any) => {
            if (work.poster_path) {
              work.poster_path = `https://image.tmdb.org/t/p/w500${work.poster_path}`;
            }
            if (work.backdrop_path) {
              work.backdrop_path = `https://image.tmdb.org/t/p/w500${work.backdrop_path}`;
            }
            return work;
          });
        }

        return person;
      });

      return {
        ...data,
        results,
      };
    } catch (error) {
      console.error("Error searching people:", error);
      // Re-throwing allows Genkit/the caller to handle it appropriately
      throw error;
    }
  }
);
