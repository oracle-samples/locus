document.addEventListener("DOMContentLoaded", () => {
  const title = document.querySelector(".md-header__ellipsis");
  if (title) {
    title.style.cursor = "pointer";
    title.addEventListener("click", () => { window.location.href = "/"; });
  }
});
