// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
{% if mintable or ownable or pausable or capped %}import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";{% endif %}
{% if burnable %}import {ERC20Burnable} from "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol";{% endif %}
{% if pausable %}import {ERC20Pausable} from "@openzeppelin/contracts/token/ERC20/extensions/ERC20Pausable.sol";{% endif %}
{% if permit %}import {ERC20Permit} from "@openzeppelin/contracts/token/ERC20/extensions/ERC20Permit.sol";{% endif %}
{% if capped %}import {ERC20Capped} from "@openzeppelin/contracts/token/ERC20/extensions/ERC20Capped.sol";{% endif %}

contract {{ CONTRACT_NAME }} is 
    ERC20{% if burnable %}, ERC20Burnable{% endif %}{% if pausable %}, ERC20Pausable{% endif %}{% if permit %}, ERC20Permit{% endif %}{% if capped %}, ERC20Capped{% endif %}{% if ownable %}, Ownable{% endif %} {
    
    {% if DECIMALS and DECIMALS != 18 %}
    uint8 private _decimals = {{ DECIMALS }};
    {% endif %}

    constructor(
        {% if ownable %}address initialOwner{% endif %}
    )
        ERC20("{{ TOKEN_NAME }}", "{{ TOKEN_SYMBOL }}")
        {% if permit %}ERC20Permit("{{ TOKEN_NAME }}"){% endif %}
        {% if capped %}ERC20Capped({{ max_supply }} * 10**decimals()){% endif %}
        {% if ownable %}Ownable(initialOwner){% endif %}
    {
        {% if INITIAL_SUPPLY and INITIAL_SUPPLY > 0 %}
        _mint({% if ownable %}initialOwner{% else %}msg.sender{% endif %}, {{ INITIAL_SUPPLY }} * 10**decimals());
        {% endif %}
    }

    {% if DECIMALS and DECIMALS != 18 %}
    function decimals() public view virtual override returns (uint8) {
        return _decimals;
    }
    {% endif %}

    {% if mintable %}
    function mint(address to, uint256 amount) public onlyOwner {
        _mint(to, amount);
    }

    function batchMint(address[] memory recipients, uint256[] memory amounts) public onlyOwner {
        require(recipients.length == amounts.length, "Arrays length mismatch");
        for (uint256 i = 0; i < recipients.length; i++) {
            _mint(recipients[i], amounts[i]);
        }
    }
    {% endif %}

    {% if pausable %}
    function pause() public onlyOwner {
        _pause();
    }

    function unpause() public onlyOwner {
        _unpause();
    }

    // Override required by Solidity for ERC20Pausable
    function _update(address from, address to, uint256 value)
        internal
        override{% if pausable and capped %}(ERC20, ERC20Pausable, ERC20Capped){% elif pausable %}(ERC20, ERC20Pausable){% elif capped %}(ERC20, ERC20Capped){% endif %}
    {
        super._update(from, to, value);
    }
    {% elif capped %}
    // Override required by Solidity for ERC20Capped
    function _update(address from, address to, uint256 value)
        internal
        override(ERC20, ERC20Capped)
    {
        super._update(from, to, value);
    }
    {% endif %}

    // Emergency functions
    {% if ownable %}
    function emergencyWithdraw() public onlyOwner {
        payable(owner()).transfer(address(this).balance);
    }

    function rescueTokens(address token, address to, uint256 amount) public onlyOwner {
        require(token != address(this), "Cannot rescue own tokens");
        IERC20(token).transfer(to, amount);
    }
    {% endif %}

    // View functions
    function getContractInfo() public view returns (
        string memory tokenName,
        string memory tokenSymbol,
        uint8 dec,
        uint256 totalSup
        {% if capped %},uint256 cap{% endif %}
        {% if ownable %},address contractOwner{% endif %}
    ) {
        return (
            name(),
            symbol(),
            decimals(),
            totalSupply(){% if capped %},
            cap(){% endif %}{% if ownable %},
            owner(){% endif %}
        );
    }
}
