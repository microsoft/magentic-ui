import jsPDF from "jspdf";

/**
 * Generates a mock resume PDF for Judy Hopps
 * @returns Blob containing the PDF file
 */
export function generateResumePDF(): Blob {
  // Create a new PDF document
  const doc = new jsPDF();

  // Add header with name and contact
  doc.setFontSize(20);
  doc.setFont("helvetica", "bold");
  doc.text("Judy Hopps", 105, 20, { align: "center" });

  doc.setFontSize(10);
  doc.setFont("helvetica", "normal");
  doc.text("judy.hopps@zootopia.gov", 105, 28, { align: "center" });
  doc.text("(555) 123-4567", 105, 33, { align: "center" });
  doc.text("Zootopia Central", 105, 38, { align: "center" });

  // Add horizontal line
  doc.setDrawColor(200, 200, 200);
  doc.line(20, 42, 190, 42);

  // Summary section
  doc.setFontSize(12);
  doc.setFont("helvetica", "bold");
  doc.text("Professional Summary", 20, 50);

  doc.setFontSize(10);
  doc.setFont("helvetica", "normal");
  doc.text(
    "Dedicated professional with over 5 years of experience in law enforcement and public service. " +
      "Skilled in investigation, problem-solving, and community outreach with a passion for making the world a better place.",
    20,
    58,
    { maxWidth: 170 }
  );

  // Education section
  doc.setFontSize(12);
  doc.setFont("helvetica", "bold");
  doc.text("Education", 20, 80);

  doc.setFontSize(10);
  doc.setFont("helvetica", "bold");
  doc.text("Zootopia Police Academy", 20, 88);

  doc.setFont("helvetica", "normal");
  doc.text("Certificate in Criminal Justice", 20, 93);
  doc.text("2016 - 2017", 20, 98);

  doc.setFont("helvetica", "bold");
  doc.text("Bunnyburrow University", 20, 106);

  doc.setFont("helvetica", "normal");
  doc.text("Bachelor of Science in Criminal Justice", 20, 111);
  doc.text("2012 - 2016", 20, 116);

  // Experience section
  doc.setFontSize(12);
  doc.setFont("helvetica", "bold");
  doc.text("Work Experience", 20, 128);

  doc.setFontSize(10);
  doc.setFont("helvetica", "bold");
  doc.text("Zootopia Police Department", 20, 136);

  doc.setFont("helvetica", "italic");
  doc.text("Detective", 20, 141);

  doc.setFont("helvetica", "normal");
  doc.text("2019 - Present", 140, 141);

  doc.text(
    "• Led investigations of high-profile cases, achieving a 95% case resolution rate\n" +
      "• Implemented new community outreach programs, improving public relations by 40%\n" +
      "• Mentored junior officers and conducted training sessions on investigative techniques",
    25,
    149,
    { maxWidth: 165 }
  );

  doc.setFont("helvetica", "bold");
  doc.text("Zootopia Police Department", 20, 169);

  doc.setFont("helvetica", "italic");
  doc.text("Patrol Officer", 20, 174);

  doc.setFont("helvetica", "normal");
  doc.text("2017 - 2019", 140, 174);

  doc.text(
    "• Patrolled assigned areas and responded to emergency calls\n" +
      "• Wrote detailed incident reports and testified in court proceedings\n" +
      "• Collaborated with community leaders to address neighborhood concerns",
    25,
    182,
    { maxWidth: 165 }
  );

  // Projects section
  doc.setFontSize(12);
  doc.setFont("helvetica", "bold");
  doc.text("Key Projects", 20, 206);

  doc.setFontSize(10);
  doc.setFont("helvetica", "bold");
  doc.text("Night Howler Investigation", 20, 214);

  doc.setFont("helvetica", "normal");
  doc.text(
    "Led a complex investigation into a citywide conspiracy, working with unlikely allies to uncover corruption " +
      "at the highest levels of government. Efforts resulted in major policy reforms and improved interspecies relations.",
    20,
    222,
    { maxWidth: 170 }
  );

  doc.setFont("helvetica", "bold");
  doc.text("Community Safety Initiative", 20, 240);

  doc.setFont("helvetica", "normal");
  doc.text(
    "Developed and implemented a community safety program in partnership with local businesses and residents. " +
      "The initiative reduced crime rates by 30% and increased community engagement in safety matters.",
    20,
    248,
    { maxWidth: 170 }
  );

  // Skills section
  doc.setFontSize(12);
  doc.setFont("helvetica", "bold");
  doc.text("Professional Skills", 20, 266);

  doc.setFontSize(10);
  doc.setFont("helvetica", "normal");
  doc.text(
    "Investigation: Criminal Profiling, Forensic Analysis, Case Documentation\n" +
      "Technology: Digital Forensics, Case Management Systems, Surveillance Tech\n" +
      "Communication: Public Speaking, Crisis Negotiation, Conflict Resolution\n" +
      "Specialties: Undercover Operations, Traffic Law, Tactical Planning",
    20,
    274,
    { maxWidth: 170 }
  );

  // Convert the PDF to a blob
  const pdfBlob = doc.output("blob");
  return pdfBlob;
}

export default generateResumePDF;
