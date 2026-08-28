import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { Scale, Menu, X, Sparkles } from 'lucide-react';

export default function Navbar() {
  const [isOpen, setIsOpen] = useState(false);

  const toggleMenu = () => setIsOpen(!isOpen);

  const navLinks = [
    { name: 'Dashboard', path: '/' },
    { name: 'Query', path: '/query' },
    { name: 'Upload', path: '/upload' },
    { name: 'Evaluation', path: '/evaluation' },
  ];

  const activeClassName = "nav-link-active";
  const inactiveClassName = "nav-link";

  return (
    <nav className="app-nav">
      <div className="container mx-auto px-4 max-w-7xl">
        <div className="flex justify-between h-[72px]">
          <div className="flex items-center">
            <NavLink to="/" className="flex items-center space-x-3 text-2xl font-bold text-slate-900 transition-opacity hover:opacity-80">
              <img src="/logo.png" alt="LexiGuard Logo" className="h-12 w-12 object-contain" />
              <span>LexiGuard</span>
            </NavLink>
          </div>

          {/* Desktop Menu */}
          <div className="hidden md:flex items-center gap-2">
            {navLinks.map((link) => (
              <NavLink
                key={link.name}
                to={link.path}
                className={({ isActive }) =>
                  `px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    isActive ? activeClassName : inactiveClassName
                  }`
                }
              >
                {link.name}
              </NavLink>
            ))}
            <NavLink to="/query" className="nav-cta">
              <Sparkles className="h-4 w-4 text-yellow-400" /> Ask LexiGuard
            </NavLink>
          </div>

          {/* Mobile Menu Button */}
          <div className="flex items-center md:hidden">
            <button
              onClick={toggleMenu}
              className="text-slate-800 hover:text-slate-900 focus:outline-none p-2"
            >
              {isOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Menu */}
      {isOpen && (
        <div className="md:hidden mobile-nav">
          <div className="px-2 pt-2 pb-3 space-y-1 sm:px-3">
            {navLinks.map((link) => (
              <NavLink
                key={link.name}
                to={link.path}
                onClick={() => setIsOpen(false)}
                className={({ isActive }) =>
                  `block px-3 py-2 rounded-md text-base font-medium ${
                    isActive ? activeClassName : inactiveClassName
                  }`
                }
              >
                {link.name}
              </NavLink>
            ))}
          </div>
        </div>
      )}
    </nav>
  );
}
