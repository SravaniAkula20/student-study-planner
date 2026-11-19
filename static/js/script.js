
// Set today's date as the earliest task deadline

const deadlineInput = document.querySelector(
    'input[name="deadline"]'
);

if (deadlineInput) {
    const today = new Date();

    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, "0");
    const day = String(today.getDate()).padStart(2, "0");

    deadlineInput.min = `${year}-${month}-${day}`;
}
