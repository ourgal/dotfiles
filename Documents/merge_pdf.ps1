# --- Configuration ---

# Set the path to pdftk.exe if it's not in your system's PATH
# Example: $pdftkPath = "C:\Program Files (x86)\PDFtk\bin\pdftk.exe"
$pdftkPath = "pdftk" # Assumes pdftk is in your PATH

# Define the output filename for the merged PDF
$outputPdfName = "output.pdf"

# --- Script Logic ---

# Get today's date in YYYYMMDD format
$today = Get-Date -Format "yyyyMMdd"

# Define the file pattern to search for
# This pattern looks for files like IMG_20260409_0001.pdf
$filePattern = "IMG_${today}_*.pdf"

# Get all PDF files matching the pattern in the current directory
$pdfFiles = Get-ChildItem -Path . -Filter $filePattern -File

# Check if any files were found
if ($pdfFiles.Count -eq 0) {
    Write-Host "No PDF files found matching the pattern 'IMG_${today}_*.pdf' in the current directory."
    exit
}

# Sort the files by name to ensure correct order
# The default sorting of Get-ChildItem should be alphabetical, which works for IMG_..._0001.pdf, IMG_..._0002.pdf etc.
$sortedPdfFiles = $pdfFiles | Sort-Object Name

# Construct the list of files for pdftk
$pdftkInputFiles = $sortedPdfFiles | ForEach-Object { $_.FullName }

# Construct the pdftk command
# The 'cat' operation merges the files. 'output' specifies the output file.
$pdftkCommand = "$pdftkPath $($pdftkInputFiles -join ' ') cat output $outputPdfName"

Write-Host "Merging the following files:"
$sortedPdfFiles | ForEach-Object { Write-Host "- $($_.Name)" }
Write-Host "Output file: $outputPdfName"

# Execute the pdftk command
try {
    # Use Invoke-Expression to execute the command string
    Invoke-Expression $pdftkCommand
    Write-Host "Successfully merged PDF files."

    # Delete the original files after successful merge
    Write-Host "Deleting original PDF files..."
    $sortedPdfFiles | ForEach-Object {
        $fileName = $_.Name
        $filePath = $_.FullName
        try {
            Remove-Item -Path $filePath -Force -ErrorAction Stop
            Write-Host "Deleted: $fileName"
        } catch {
            Write-Error "Failed to delete '$fileName': $($_.Exception.Message)"
        }
    }
    Write-Host "All original PDF files have been deleted."

} catch {
    Write-Error "An error occurred during PDF merging: $($_.Exception.Message)"
    Write-Error "Please ensure pdftk is installed and in your PATH, or update the `$pdftkPath` variable."
}
