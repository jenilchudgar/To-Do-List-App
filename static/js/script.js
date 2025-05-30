document.getElementById("input1").focus()
function handleInput(index) {
    const inputs = document.querySelectorAll('.inputContainer input');
    const current = inputs[index];
    const next = inputs[index + 1];

    if (current.value.length === 1 && next) {
        next.disabled = false;
        next.focus();
    }

    checkAllInputsFilled(inputs);
}

function handleBackspace(index, event) {
    const inputs = document.querySelectorAll('.inputContainer input');
    const current = inputs[index];
    const prev = inputs[index - 1];

    if (event.key === 'Backspace' && current.value === '' && prev) {
        current.disabled = true;
        prev.focus();
    }

    checkAllInputsFilled(inputs);
}

function checkAllInputsFilled(inputs) {
    const allFilled = Array.from(inputs).every(input => input.value.length === 1);
    const btn = document.querySelector('.verify');
    btn.disabled = !allFilled;
    btn.style.cursor = allFilled ? 'pointer' : 'not-allowed';
}
