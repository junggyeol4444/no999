document.addEventListener('DOMContentLoaded', () => {
  if (window.lucide) window.lucide.createIcons();

  const dialog = document.querySelector('#projectDialog');
  document.querySelector('#newProject').addEventListener('click', () => dialog.showModal());

  const sidebar = document.querySelector('#sidebar');
  const overlay = document.querySelector('#mobileOverlay');
  const toggleMenu = () => {
    sidebar.classList.toggle('open');
    overlay.classList.toggle('show');
  };
  document.querySelector('#menuButton').addEventListener('click', toggleMenu);
  overlay.addEventListener('click', toggleMenu);

  document.querySelectorAll('.nav-item[href]').forEach((item) => {
    item.addEventListener('click', () => {
      document.querySelectorAll('.nav-item').forEach((nav) => nav.classList.remove('active'));
      item.classList.add('active');
      if (window.innerWidth <= 720 && sidebar.classList.contains('open')) toggleMenu();
    });
  });

  document.querySelector('.modal .primary-button').addEventListener('click', () => {
    const title = document.querySelector('.modal input').value.trim();
    if (title) localStorage.setItem('novelFactoryDraftTitle', title);
  });
});
