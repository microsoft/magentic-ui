# @yaml
# signature: search_dir <search_term> [<dir>]
# docstring: searches for search_term in all files in dir. If dir is not provided, searches in the current directory
# arguments:
#   search_term:
#     type: string
#     description: the term to search for
#     required: true
#   dir:
#     type: string
#     description: the directory to search in (if not provided, searches in the current directory)
#     required: false

# Called via: source search.sh && search_dir "term" "/path"

search_dir() {
    if [ $# -eq 1 ]; then
        local search_term="$1"
        local dir="./"
    elif [ $# -eq 2 ]; then
        local search_term="$1"
        # Expand leading ~ since bash doesn't expand inside quoted vars.
        local raw_dir="${2/#\~/$HOME}"
        if [ -d "$raw_dir" ]; then
            local dir="$raw_dir"
        else
            echo "Directory $2 not found"
            return
        fi
    else
        echo "Usage: search_dir <search_term> [<dir>]"
        return
    fi
    dir=$(realpath "$dir")
    local matches=$(find "$dir" -type f ! -path '*/.*' -exec grep -nIH -- "$search_term" {} + | cut -d: -f1 | sort | uniq -c)
    # if no matches, return
    if [ -z "$matches" ]; then
        echo "No matches found for \"$search_term\" in $dir"
        return
    fi
    # Calculate total number of matches
    local num_matches=$(echo "$matches" | awk '{sum+=$1} END {print sum}')
    # calculate total number of files matched
    local num_files=$(echo "$matches" | wc -l | awk '{$1=$1; print $0}')
    # if num_files is > 100, print an error
    if [ $num_files -gt 100 ]; then
        echo "More than $num_files files matched for \"$search_term\" in $dir. Please narrow your search."
        return
    fi

    echo "Found $num_matches matches for \"$search_term\" in $dir:"
    echo "$matches" | awk '{$2=$2; gsub(/^\.+\/+/, "./", $2); print $2 " ("$1" matches)"}'
    echo "End of matches for \"$search_term\" in $dir"
}

search_file() {
    # Check if the first argument is provided
    if [ -z "$1" ]; then
        echo "Usage: search_file <search_term> [<file>]"
        return
    fi
    # Check if the second argument is provided
    if [ -n "$2" ]; then
        # Check if the provided argument is a valid file
        if [ -f "$2" ]; then
            local file="$2"  # Set file if valid
        else
            echo "Usage: search_file <search_term> [<file>]"
            echo "Error: File name $2 not found. Please provide a valid file name."
            return  # Exit if the file is not valid
        fi
    else
        # Check if a file is open
        if [ -z "$CURRENT_FILE" ]; then
            echo "No file open. Use the open command first."
            return  # Exit if no file is open
        fi
        local file="$CURRENT_FILE"  # Set file to the current open file
    fi
    local search_term="$1"
    file=$(realpath "$file")
    # Use grep to directly get the desired formatted output
    local matches=$(grep -nH -- "$search_term" "$file")
    # Check if no matches were found
    if [ -z "$matches" ]; then
        echo "No matches found for \"$search_term\" in $file"
        return
    fi
    # Calculate total number of matches
    local num_matches=$(echo "$matches" | wc -l | awk '{$1=$1; print $0}')

    # calculate total number of lines matched
    local num_lines=$(echo "$matches" | cut -d: -f1 | sort | uniq | wc -l | awk '{$1=$1; print $0}')
    # if num_lines is > 100, print an error
    if [ $num_lines -gt 100 ]; then
        echo "More than $num_lines lines matched for \"$search_term\" in $file. Please narrow your search."
        return
    fi

    # Print the total number of matches and the matches themselves
    echo "Found $num_matches matches for \"$search_term\" in $file:"
    echo "$matches" | cut -d: -f1-2 | sort -u -t: -k2,2n | while IFS=: read -r filename line_number; do
        echo "Line $line_number:$(sed -n "${line_number}p" "$file")"
    done
    echo "End of matches for \"$search_term\" in $file"
}

find_file() {
    if [ $# -eq 1 ]; then
        local file_name="$1"
        local dir="./"
    elif [ $# -eq 2 ]; then
        local file_name="$1"
        # Expand leading ~ since bash doesn't expand inside quoted vars.
        local raw_dir="${2/#\~/$HOME}"
        if [ -d "$raw_dir" ]; then
            local dir="$raw_dir"
        else
            echo "Directory $2 not found"
            return
        fi
    else
        echo "Usage: find_file <file_name> [<dir>]"
        return
    fi

    dir=$(realpath "$dir")
    # Prune venv internals to keep search results clean.
    local matches=$(find "$dir" \
        \( -path '*/__pycache__' -o -path '*/site-packages' \) -prune \
        -o -type f -name "$file_name" -print)
    # if no matches, return
    if [ -z "$matches" ]; then
        echo "No matches found for \"$file_name\" in $dir"
        return
    fi
    # Calculate total number of matches
    local num_matches=$(echo "$matches" | wc -l | awk '{$1=$1; print $0}')
    echo "Found $num_matches matches for \"$file_name\" in $dir:"
    echo "$matches" | awk '{print $0}'
}
